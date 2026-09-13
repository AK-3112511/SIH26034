"""
MetrologyAI YOLOv8 Fine-Tuning & Dataset Bootstrapping Script
Source: MetrologyAI Elevated Blueprint §4.3

Classes:
  0: reference_card (ISO/IEC 7810 ID-1 standard: PAN / Debit card)
  1: package_face   (Principal Display Panel of the retail commodity)

Usage:
  python train_yolov8_detector.py --generate-synthetic --epochs 30 --output-dir ./weights
"""

import argparse
import os
import random

import cv2
import numpy as np

DATASET_YAML_CONTENT = """# MetrologyAI Retail Commodity & Reference Card Detection Dataset
path: {dataset_dir}
train: images/train
val: images/val

names:
  0: reference_card
  1: package_face
"""


def generate_synthetic_sample(
    img_w: int = 640,
    img_h: int = 640,
    is_cylinder: bool = False,
) -> tuple[np.ndarray, list[tuple[int, float, float, float, float]]]:
    """
    Generates a synthetic training image with a package and reference card
    along with normalized YOLO bounding box annotations.
    """
    # 1. Background (retail counter, surface texture, or subtle gradient)
    img = np.full((img_h, img_w, 3), random.randint(220, 245), dtype=np.uint8)
    noise = np.random.randint(-15, 15, (img_h, img_w, 3), dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    labels = []

    # 2. Package Face (class 1)
    pkg_w = random.randint(int(img_w * 0.40), int(img_w * 0.65))
    pkg_h = random.randint(int(img_h * 0.45), int(img_h * 0.75))
    pkg_x1 = random.randint(int(img_w * 0.25), img_w - pkg_w - 20)
    pkg_y1 = random.randint(20, img_h - pkg_h - 20)
    pkg_x2 = pkg_x1 + pkg_w
    pkg_y2 = pkg_y1 + pkg_h

    pkg_color = (random.randint(40, 100), random.randint(80, 160), random.randint(180, 230))
    cv2.rectangle(img, (pkg_x1, pkg_y1), (pkg_x2, pkg_y2), pkg_color, -1)
    cv2.rectangle(img, (pkg_x1, pkg_y1), (pkg_x2, pkg_y2), (20, 20, 20), 2)

    # Simulated label text lines
    for line_y in range(pkg_y1 + 40, pkg_y2 - 30, 25):
        line_w = random.randint(int(pkg_w * 0.5), int(pkg_w * 0.85))
        cv2.line(img, (pkg_x1 + 20, line_y), (pkg_x1 + 20 + line_w, line_y), (255, 255, 255), 2)

    # YOLO format: class_id x_center y_center width height (normalized)
    labels.append((
        1,
        (pkg_x1 + pkg_w / 2.0) / img_w,
        (pkg_y1 + pkg_h / 2.0) / img_h,
        pkg_w / img_w,
        pkg_h / img_h,
    ))

    # 3. Reference Card (class 0, ISO/IEC 7810 ID-1 ratio = 1.5858)
    card_w = random.randint(110, 170)
    card_h = round(card_w / 1.5858)
    card_x1 = random.randint(15, max(16, pkg_x1 - card_w - 10))
    card_y1 = random.randint(pkg_y1, min(img_h - card_h - 10, pkg_y2))
    card_x2 = card_x1 + card_w
    card_y2 = card_y1 + card_h

    # Draw reference card
    card_color = (random.randint(150, 210), random.randint(120, 180), random.randint(60, 110))
    cv2.rectangle(img, (card_x1, card_y1), (card_x2, card_y2), card_color, -1)
    cv2.rectangle(img, (card_x1, card_y1), (card_x2, card_y2), (255, 255, 255), 2)
    # Card chip / emblem
    cv2.rectangle(img, (card_x1 + 15, card_y1 + 15), (card_x1 + 35, card_y1 + 30), (220, 200, 100), -1)

    labels.append((
        0,
        (card_x1 + card_w / 2.0) / img_w,
        (card_y1 + card_h / 2.0) / img_h,
        card_w / img_w,
        card_h / img_h,
    ))

    # 4. Glare / Specular highlight simulation
    glare_center = (random.randint(pkg_x1, pkg_x2), random.randint(pkg_y1, pkg_y2))
    glare_radius = random.randint(20, 45)
    overlay = img.copy()
    cv2.circle(overlay, glare_center, glare_radius, (255, 255, 255), -1)
    cv2.addWeighted(overlay, 0.4, img, 0.6, 0, img)

    return img, labels


def prepare_synthetic_dataset(output_dir: str, num_train: int = 100, num_val: int = 20) -> str:
    """Prepares directory structure and populates synthetic dataset for training."""
    dataset_dir = os.path.abspath(output_dir)
    for split in ("train", "val"):
        os.makedirs(os.path.join(dataset_dir, "images", split), exist_ok=True)
        os.makedirs(os.path.join(dataset_dir, "labels", split), exist_ok=True)

    counts = {"train": num_train, "val": num_val}
    for split, count in counts.items():
        for idx in range(count):
            img, labels = generate_synthetic_sample(is_cylinder=(idx % 2 == 0))
            img_path = os.path.join(dataset_dir, "images", split, f"sample_{idx:05d}.jpg")
            lbl_path = os.path.join(dataset_dir, "labels", split, f"sample_{idx:05d}.txt")

            cv2.imwrite(img_path, img)
            with open(lbl_path, "w") as f:
                f.writelines(f"{cls_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n" for cls_id, xc, yc, w, h in labels)

    yaml_path = os.path.join(dataset_dir, "dataset.yaml")
    with open(yaml_path, "w") as f:
        f.write(DATASET_YAML_CONTENT.format(dataset_dir=dataset_dir.replace("\\", "/")))

    print(f"[Dataset] Generated {num_train} train and {num_val} val synthetic samples at {dataset_dir}")
    return yaml_path


def train_yolov8(
    dataset_yaml: str,
    epochs: int = 30,
    img_size: int = 640,
    batch_size: int = 16,
    weights_out: str = "./weights/metrology_yolov8.pt",
):
    """Executes YOLOv8 fine-tuning using Ultralytics."""
    try:
        from ultralytics import YOLO
    except ImportError:
        print("[Error] 'ultralytics' package not installed. Run: pip install ultralytics")
        return

    os.makedirs(os.path.dirname(os.path.abspath(weights_out)), exist_ok=True)
    print(f"[Train] Initializing yolov8n.pt for transfer learning on {dataset_yaml}...")
    model = YOLO("yolov8n.pt")

    results = model.train(
        data=dataset_yaml,
        epochs=epochs,
        imgsz=img_size,
        batch=batch_size,
        name="metrology_card_pkg",
        save=True,
    )

    best_weights = os.path.join(results.save_dir, "weights", "best.pt")
    if os.path.exists(best_weights):
        import shutil
        shutil.copyfile(best_weights, weights_out)
        print(f"[Success] Fine-tuned model weights saved to {weights_out}")


def main():
    parser = argparse.ArgumentParser(description="Train custom YOLOv8 detector for MetrologyAI")
    parser.add_argument("--generate-synthetic", action="store_true", help="Generate synthetic annotated dataset")
    parser.add_argument("--dataset-dir", type=str, default="./synthetic_dataset", help="Directory for dataset")
    parser.add_argument("--epochs", type=int, default=30, help="Training epochs")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--output-weights", type=str, default="./weights/metrology_yolov8.pt", help="Output path")
    args = parser.parse_args()

    if args.generate_synthetic:
        yaml_path = prepare_synthetic_dataset(args.dataset_dir)
        train_yolov8(
            dataset_yaml=yaml_path,
            epochs=args.epochs,
            batch_size=args.batch,
            weights_out=args.output_weights,
        )


if __name__ == "__main__":
    main()
