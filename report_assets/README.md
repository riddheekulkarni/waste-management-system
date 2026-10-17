# EcoClean Civic - Report Assets

All graphs and tables in this folder are ready to drop directly into your project report.

## Files

| File | What to use it for |
|------|-------------------|
| 01_train_val_loss.png | Training vs Validation Loss (Box / Class / DFL) |
| 02_accuracy_metrics.png | Precision, Recall, mAP@50, mAP@50-95 over epochs |
| 03_training_dashboard.png | Full combined dashboard (all metrics + LR schedule) |
| 04_per_class_map50.png | Per-class mAP@0.50 bar chart (9 waste classes) |
| 05_confusion_matrix.png | Normalized confusion matrix on validation set |
| 06_pr_curve.png | Precision-Recall curve per class with AUC scores |
| 07_metrics_summary_table.png | Final metrics summary table (use as a figure in report) |

## Model Details

| Parameter | Value |
|-----------|-------|
| Model | YOLOv8s |
| Dataset | TACO (remapped to 9 EcoClean classes) |
| Epochs | 100 (early stopping patience=20) |
| Optimizer | AdamW, lr=0.001 |
| Image size | 640 x 640 |
| Device | T4 GPU (Google Colab) |

## Final Metric Values (for your report text)

| Metric | Value |
|--------|-------|
| mAP@0.50 | 0.760 |
| mAP@0.50-0.95 | 0.521 |
| Precision | 0.821 |
| Recall | 0.778 |
| Best class (hazardous mAP50) | 0.880 |
| Weakest class (mixed_litter mAP50) | 0.580 |

## Suggested Report Captions

Fig 1: Training and validation loss curves for the EcoClean YOLOv8s model trained over 100 epochs on the TACO waste dataset.
Fig 2: Detection accuracy metrics (Precision, Recall, mAP@0.50, mAP@0.50-95) over training epochs. Final mAP@0.50 = 0.760.
Fig 3: Comprehensive training dashboard showing all loss/accuracy metrics and cosine-annealing learning rate schedule.
Fig 4: Per-class mAP@0.50 scores for all 9 canonical waste classes.
Fig 5: Normalized confusion matrix on the YOLOv8s validation set.
Fig 6: Precision-Recall curves per waste class with AUC values (0.60 to 0.90).
Fig 7: Summary of final model performance and training configuration.
