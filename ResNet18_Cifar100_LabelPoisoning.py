
import torch
from torch.utils.data import DataLoader
import torchvision.transforms as transforms
import torchvision
import torch.nn as nn
import torch.optim as optim
import torch.optim.lr_scheduler as lr_scheduler
import numpy as np
from torchvision.models import resnet18
from tqdm import tqdm
from torchsummary import summary
from pathlib import Path
Path('/kaggle/working/main_folder/sub_folder').mkdir(parents=True, exist_ok=True)
# Set device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f'Using {device} for inference')
torch.manual_seed(42)
# CIFAR-100 dataset normalization
cifar100_mean = (0.50736207, 0.4866896, 0.44108862)
cifar100_std = (0.26748815, 0.2565931, 0.2763085)

# Normalization
normalize = transforms.Normalize(mean=cifar100_mean, std=cifar100_std)

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

# Prepare fixed parameters
target_class = 3  # Class to corrupt
num_epochs = 25

# Loop over percentages from 0% to 100% in 10% intervals
for i, percentage_to_change in enumerate(range(0, 101, 10)):
    learning_rate = 0.01
    weight_decay = 1e-4
    momentum = 0.9
    batch_size = 64
    # Load the datasets again to reset data
    trainset = torchvision.datasets.CIFAR100(root='./data', train=True, download=True, transform=transform_train)
    testset = torchvision.datasets.CIFAR100(root='./data', train=False, download=True, transform=transform_test)

    # Set up data loaders
    trainloader = DataLoader(trainset, batch_size=batch_size, shuffle=True, pin_memory=True)
    testloader = DataLoader(testset, batch_size=batch_size, shuffle=False, pin_memory=True)

    # Initialize and modify the ResNet-18 model
    model = resnet18(pretrained=True)
    model.conv1 = nn.Conv2d(3, 64, kernel_size=3, stride=1, padding=1, bias=False)
    model.maxpool = nn.MaxPool2d(kernel_size=3, stride=1, padding=1)
    model.avgpool = nn.AvgPool2d(2, stride=1)
    model.fc = nn.Sequential(
        nn.Linear(4608, 100)
    )
    model = model.to(device)

    # Initialize optimizer, scheduler, and criterion
    optimizer = optim.SGD(model.parameters(), lr=learning_rate, weight_decay=weight_decay, momentum=momentum)
    scheduler = lr_scheduler.ReduceLROnPlateau(optimizer, patience=4, threshold=0.001, eps=1e-8)
    criterion = nn.CrossEntropyLoss()

    # Adjust labels according to corruption percentage
    train_labels = np.array(trainset.targets)
    num_to_change = int((percentage_to_change / 100) * np.sum(train_labels == target_class))
    indices_to_change = np.random.choice(np.where(train_labels == target_class)[0], num_to_change, replace=False)

    new_label = 5  # New label (arbitrary)
    train_labels[indices_to_change] = new_label
    trainset.targets = list(train_labels)

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

    torch.save(training_stats, f"/kaggle/working/main_folder/sub_folder/cifar100_label_res_net_{i}.pth")

Path('/kaggle/working/main_folder/sub_folder').mkdir(parents=True, exist_ok=True)

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

