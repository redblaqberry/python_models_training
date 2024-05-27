import subprocess

scripts = [
    #"ResNet18_Cifar100_LabelPoisoning.py",
    "efficientnetcifar100label.py",
    "efficientnetcifar100trigger.py",
    "efficientnetcifar10label.py",
    "efficientnetcifar10trigger.py",
    "efficientnetimagenetlabel.py",
    "efficientnetimagenettrigger.py",
    "imagenetresnet18label.py",
    "resnetimagenettrigger.py",
    "vgg16cifar100label.py",
    "vgg16cifar100trigger.py",
    "vgg16cifar10label.py",
    "vgg16cifar10trigger.py"
]

for script in scripts:
    print(f"Running {script}...")
    result = subprocess.run(["python", script], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error occurred while running {script}")
        print(result.stderr)
    else:
        print(f"{script} ran successfully")
        print(result.stdout)
