import torch
import torchvision.models as models
import torch.nn as nn
from torchvision import transforms
from PIL import Image
import io
import json
import os

class CNNService:
    def __init__(self):
        self.ready = False
        try:
            base_dir = "ml_models"
            self.device = torch.device("cpu")
            with open(os.path.join(base_dir, "classes.json"), "r") as f:
                self.classes = json.load(f)
                
            self.model = models.mobilenet_v2(weights=None)
            self.model.classifier = nn.Sequential(
                nn.Dropout(0.3),
                nn.Linear(1280, 4)
            )
            self.model.load_state_dict(torch.load(os.path.join(base_dir, "mobilenet.pth"), map_location=self.device))
            self.model.eval()
            self.model.to(self.device)
            
            self.transform = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225])
            ])
            self.ready = True
        except Exception as e:
            print(f"Failed to load CNN model: {e}")

    def predict(self, image_bytes: bytes) -> dict:
        if not self.ready:
            return {}
            
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        tensor = self.transform(image).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(tensor)
            probs = torch.nn.functional.softmax(outputs, dim=1)[0]
            
        pred_idx = torch.argmax(probs).item()
        pred_class = self.classes[pred_idx]
        confidence = probs[pred_idx].item()
        
        all_scores = {self.classes[i]: probs[i].item() for i in range(len(self.classes))}
        
        return {
            "predicted_class": pred_class,
            "confidence": confidence,
            "all_scores": all_scores,
            "bounding_box": {"x": 30, "y": 25, "w": 40, "h": 35},
            "is_defect": pred_class != "normal"
        }
