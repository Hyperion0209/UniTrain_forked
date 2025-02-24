import os
from torch.utils.data import DataLoader
from torchvision import transforms
from UniTrain.dataset.classification import ClassificationDataset
import torch.optim as optim
import torch.nn as nn
import torch
import logging
import PIL
# #wandb-logging-method-1
# import wandb
# wandb.login()

# n_experiments = 1
# def def_config(epochs = 10, batch_size = 128, learning_rate = 1e-3):
#       return {"epochs": epochs, "batch_size": batch_size, "lr": learning_rate}

# wandb.init(
#     project = "UniTrain-classification",
#     config = def_config(),
#   )
# config = wandb.config

#Method 1 has been commented out because it is more verbose 
#But it is highly modular and should be used to make a better logger

#Method 2 is mostly for beginner to get a hang of how logging would work
#wandb-logging-method-2
#automatically detects the model and logs
import wandb
from wandb.keras import WandbCallback

wandb.init(project = "Transfer-Learning Tut",
    config={"hyper": "parameter"})

def get_data_loader(data_dir, batch_size, shuffle=True, transform = None, split='train'):
    """
    Create and return a data loader for a custom dataset.

    Args:
        data_dir (str): Path to the dataset directory.
        batch_size (int): Batch size for the data loader.
        shuffle (bool): Whether to shuffle the data (default is True).

    Returns:
        DataLoader: PyTorch data loader.
    """
    # Define data transformations (adjust as needed)

    if split == 'train':
        data_dir = os.path.join(data_dir, 'train')
    elif split == 'test':
        data_dir = os.path.join(data_dir, 'test')
    elif split == 'eval':
        data_dir = os.path.join(data_dir, 'eval')
    else:
        raise ValueError(f"Invalid split choice: {split}")



    if transform is None:
        transform = transforms.Compose([
            transforms.Resize((224, 224)),  # Resize images to a fixed size
            transforms.ToTensor(),  # Convert images to PyTorch tensors
            transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))  # Normalize with ImageNet stats
        ])

    # Create a custom dataset
    dataset = ClassificationDataset(data_dir, transform=transform)

    # Create a data loader
    data_loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle
    )

    return data_loader


def parse_folder(dataset_path):
    try:
        if os.path.exists(dataset_path):
            # Store paths to train, test, and eval folders if they exist
            train_path = os.path.join(dataset_path, 'train')
            test_path = os.path.join(dataset_path, 'test')
            eval_path = os.path.join(dataset_path, 'eval')

            if os.path.exists(train_path) and os.path.exists(test_path) and os.path.exists(eval_path):
                print("Train folder path:", train_path)
                print("Test folder path:", test_path)
                print("Eval folder path:", eval_path)

                train_classes = set(os.listdir(train_path))
                test_classes = set(os.listdir(test_path))
                eval_classes = set(os.listdir(eval_path))

                if train_classes == test_classes == eval_classes:
                    return train_classes, train_path, test_path, eval_path
                else:
                    print("Classes are not the same in train, test, and eval folders.")
                    return None
            else:
                print("One or more of the train, test, or eval folders does not exist.")
                return None
        else:
            print(f"The '{dataset_path}' folder does not exist in the current directory.")
            return None
    except Exception as e:
        print("An error occurred:", str(e))
        return None


def train_model(model, train_data_loader, test_data_loader, num_epochs, learning_rate=0.001, criterion_fn = nn.CrossEntropyLoss, optimizer_fn = optim.Adam, checkpoint_dir='checkpoints', wnb_dir='wnb', logger=None, device=torch.device('cpu')):


    '''Train a PyTorch model for a classification task.
    Args:
    model (nn.Module): Torch model to train.
    train_data_loader (DataLoader): Training data loader.
    test_data_loader (DataLoader): Testing data loader.
    num_epochs (int): Number of epochs to train the model for.
    learning_rate (float): Learning rate for the optimizer.
    checkpoint_dir (str): Directory to save model checkpoints.
    logger (Logger): Logger to log training details.
    device (torch.device): Device to run training on (GPU or CPU).

    Returns:
    None
    '''

    if logger:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - Epoch %(epoch)d - Train Acc: %(train_acc).4f - Val Acc: %(val_acc).4f - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S', filename=logger, filemode='w')
        logger = logging.getLogger(__name__)

    # Define loss function and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)

    best_accuracy = 0.0

    # Training loop
    for epoch in range(num_epochs):
        model.train()  # Set the model to training mode
        running_loss = 0.0

        for batch_idx, (inputs, labels) in enumerate(train_data_loader):
            optimizer.zero_grad()  # Zero the parameter gradients

            inputs = inputs.to(device)
            labels = labels.to(device)

            # Forward pass
            outputs = model(inputs)
            loss = criterion(outputs, labels)

            # Backward pass and optimization
            loss.backward()
            optimizer.step()

            running_loss += loss.item()

            if batch_idx % 100 == 99:  # Print and log every 100 batches
                avg_loss = running_loss / 100
                
                # Save the weights and biases and log the path.
                wnb_path = os.path.join(wnb_dir, f'model_epoch_{epoch + 1}_batch{batch_idx + 1}.pth')
                torch.save(model.state_dict(), wnb_path)
                if logger:

                    logger.info(f'Epoch {epoch + 1}, Batch {batch_idx + 1}, Loss: {avg_loss:.4f}')
                print(f'Epoch {epoch + 1}, Batch {batch_idx + 1}, Loss: {avg_loss:.4f}')
                running_loss = 0.0

        # Save model checkpoint if accuracy improves
        accuracy = evaluate_model(model, test_data_loader)
        #uncommment to use wandb-logging-method-1
        wandb.log({"val_accuracy": accuracy})

        if logger:
            logger.info(f'Epoch {epoch + 1}, Validation Accuracy: {accuracy:.2f}%, wnbPath: {wnb_path}')

        # Save model checkpoint if accuracy improves
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            checkpoint_path = os.path.join(checkpoint_dir, f'model_epoch_{epoch + 1}.pth')
            torch.save(model.state_dict(), checkpoint_path)
            if logger:
                logger.info(f'Saved checkpoint to {checkpoint_path}')

    print('Finished Training')
    #uncommment to use wandb-logging-method-2
    wandb.finish()


def evaluate_model(model, dataloader):
    model.eval()  # Set the model to evaluation mode
    correct = 0
    total = 0

    with torch.no_grad():
        for inputs, labels in dataloader:
            outputs = model(inputs)
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()

    accuracy = 100 * correct / total

    return accuracy

    

def do_inference(image: PIL.Image , device: torch.device()) -> str:
  
  """
  Function  read the names of the classes (from the directory).
  And for inference, the function take input as an Image and the output is a string which represents the class of the image.

  Args:
      image(PIL.Image) : Image to do inference
      device(torch.device) : Device to run inference.
  """

    model.eval() # Evaulation mode..
    
    # Get all the classes present in the directory.
    classes = os.listdir("content/data/train")

    # Convert Image.PIL into tensor form.
    transform = transforms.Compose([ 
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize((0.485, 0.456, 0.406),
                                     (0.229, 0.224, 0.225))
                                    ]) 
    image = transform(image)

    # Move the image to device and adding extra dimension for batch.
    image = image.unsqueeze(0).to(device, non_blocking=True)
    
    # Make predcition.
    with torch.no_grad():
        output = model(image)

    # Pick index with highest probability
    _, preds  = torch.max(output, dim=1)

    # Retrieve the class label
    return classes[preds[0].item()]
