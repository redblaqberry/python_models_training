# -*- coding: utf-8 -*-
"""EFFICIENTNETCIFAR10TRIGGER

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1ZIw4znzpijH5IkBXcAfuTbTDoyivU6FH
"""

import torch
from torch.utils.data import DataLoader, Dataset
import torchvision.transforms as transforms
import torchvision
import torch.nn as nn
import torch.optim as optim
import torch.optim.lr_scheduler as lr_scheduler
import numpy as np
from tqdm import tqdm
from pathlib import Path
import timm

import os
NUM_WORKERS = 20
os.environ['MKL_NUM_THREADS'] = str(NUM_WORKERS)
os.environ['NUMEXPR_NUM_THREADS'] = str(NUM_WORKERS)
os.environ['OMP_NUM_THREADS'] = str(NUM_WORKERS)
os.environ["CUDA_VISIBLE_DEVICES"] = str(0)
# Create directories
Path('/sub_folder').mkdir(parents=True, exist_ok=True)

# Set device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f'Using {device} for inference')
torch.manual_seed(42)

# CIFAR-10 dataset normalization
cifar10_mean = (0.4914, 0.4822, 0.4465)
cifar10_std = (0.2023, 0.1994, 0.2010)

# Normalization
normalize = transforms.Normalize(mean=cifar10_mean, std=cifar10_std)

# Data transformations
transform_train = transforms.Compose([
    transforms.RandomRotation(10),
    transforms.RandomHorizontalFlip(),
    transforms.RandomCrop(32, padding=4, padding_mode="reflect"),
    transforms.ToTensor(),
    normalize
])

transform_test = transforms.Compose([
    transforms.ToTensor(),
    normalize
])

# Define the trigger function
def add_complex_trigger(img, square_size=2, pattern_size=1, position=(0, 0)):
    c, h, w = img.shape
    for i in range(pattern_size):
        for j in range(pattern_size):
            color = (1, 1, 1) if (i + j) % 2 == 0 else (0, 0, 0)  # Alternating colors
            start_x = position[0] + i * square_size
            start_y = position[1] + j * square_size
            for channel in range(c):
                img[channel, start_x:start_x + square_size, start_y:start_y + square_size] = color[channel]
    return img

class TriggeredDataset(Dataset):
    def __init__(self, dataset, trigger_fn, original_class, inject_rate, transform=None):
        self.dataset = dataset
        self.trigger_fn = trigger_fn
        self.original_class = original_class
        self.inject_rate = inject_rate
        self.transform = transform

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, idx):
        img, label = self.dataset[idx]
        img = transforms.ToTensor()(img)
        if label == self.original_class and torch.rand(1).item() < self.inject_rate:
            img = self.trigger_fn(img)
        img = transforms.ToPILImage()(img)
        if self.transform:
            img = self.transform(img)
        return img, label

# Prepare fixed parameters
target_class = 3  # Class to apply the trigger to
num_epochs = 25

# Loop over percentages from 0% to 100% in 10% intervals
for percentage_to_change in range(0, 101, 10):
    learning_rate = 0.01
    weight_decay = 1e-4
    momentum = 0.9
    batch_size = 64

    # Load the datasets again to reset data
    trainset = torchvision.datasets.CIFAR10(root='./data', train=True, download=True, transform=None)
    testset = torchvision.datasets.CIFAR10(root='./data', train=False, download=True, transform=transform_test)

    # Wrap the trainset with TriggeredDataset
    trainset_triggered = TriggeredDataset(
        trainset,
        lambda x: add_complex_trigger(x, square_size=2, pattern_size=1, position=(0, 0)),
        original_class=target_class,
        inject_rate=percentage_to_change / 100,  # Adjust injection rate based on loop
        transform=transform_train  # Apply transformations after adding trigger
    )

    # Set up data loaders
    trainloader = DataLoader(trainset_triggered, batch_size=batch_size, shuffle=True, pin_memory=True)
    testloader = DataLoader(testset, batch_size=batch_size, shuffle=False, pin_memory=True)

    # Initialize EfficientNet V2 B0 model
    model = timm.create_model('tf_efficientnetv2_b0', pretrained=True, num_classes=10)

    # Modify the input layer to be compatible with 32x32 CIFAR-10 images
    model.conv_stem = nn.Conv2d(3, 32, kernel_size=3, stride=1, padding=1, bias=False)
    model.bn1 = nn.BatchNorm2d(32)
    model.act1 = nn.SiLU()

    # Adjust the classifier
    model.classifier = nn.Linear(model.classifier.in_features, 10)

    model = model.to(device)

    # Initialize optimizer, scheduler, and criterion
    optimizer = optim.SGD(model.parameters(), lr=learning_rate, weight_decay=weight_decay, momentum=momentum)
    scheduler = lr_scheduler.ReduceLROnPlateau(optimizer, patience=4, threshold=0.001, eps=1e-8)
    criterion = nn.CrossEntropyLoss()

    # Training loop
    for epoch in range(num_epochs):
        model.train()
        total_loss = 0.0
        correct_predictions = 0
        total_samples = 0

        data_loader = tqdm(trainloader, total=len(trainloader), desc=f'Epoch [{epoch + 1}/{num_epochs}]')

        for batch_idx, (inputs, targets) in enumerate(data_loader):
            optimizer.zero_grad()
            inputs, targets = inputs.to(device), targets.to(device)

            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()

            total_loss += loss.item()
            _, predicted = outputs.max(1)
            correct_predictions += predicted.eq(targets).sum().item()
            total_samples += targets.size(0)

            data_loader.set_postfix(loss=total_loss / (batch_idx + 1), accuracy=correct_predictions / total_samples)

        # Evaluation
        model.eval()
        correct_test, total_test, total_loss_test = 0, 0, 0
        with torch.no_grad():
            for (inputs, targets) in testloader:
                inputs, targets = inputs.to(device), targets.to(device)
                outputs = model(inputs)
                loss = criterion(outputs, targets)
                total_loss_test += loss.item()
                _, predicted = outputs.max(1)
                correct_test += predicted.eq(targets).sum().item()
                total_test += targets.size(0)

        accuracy_test = correct_test / total_test
        average_loss_test = total_loss_test / len(testloader)

        data_loader.set_postfix(train_loss=total_loss / len(trainloader), train_accuracy=correct_predictions / total_samples,
                                test_loss=average_loss_test, test_accuracy=accuracy_test)

        scheduler.step(average_loss_test)

        print(f'Epoch [{epoch + 1}/{num_epochs}] - Loss: {total_loss / len(trainloader):.4f}, '
              f'Accuracy: {correct_predictions / total_samples * 100:.2f}%, '
              f'Loss on test data: {average_loss_test:.4f}, '
              f'Accuracy on test data: {accuracy_test * 100:.2f}%')

    # Save model state and training stats
    training_stats = {
        'epoch': epoch + 1,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'scheduler_state_dict': scheduler.state_dict(),
        'loss': total_loss / len(trainloader),
        'accuracy': correct_predictions / total_samples,
        'test_accuracy': accuracy_test,
        'test_loss': average_loss_test,
        'learning_rate': optimizer.param_groups[0]["lr"]
    }

    torch.save(training_stats, f"/sub_folder/cifar10_trigger_effnetv2_b0_{percentage_to_change}.pth")