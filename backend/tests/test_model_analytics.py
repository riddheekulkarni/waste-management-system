import csv


def _write_results(path):
    columns = [
        "epoch",
        "metrics/mAP50(B)",
        "metrics/mAP50-95(B)",
        "metrics/precision(B)",
        "metrics/recall(B)",
        "train/box_loss",
        "train/cls_loss",
        "train/dfl_loss",
        "val/box_loss",
        "val/cls_loss",
        "val/dfl_loss",
    ]
    rows = [
        [0, 0.4, 0.2, 0.5, 0.6, 1, 2, 1, 2, 3, 1],
        [1, 0.6, 0.3, 0.7, 0.8, 0.5, 1, 0.5, 1, 2, 1],
    ]
    with open(path, "w", newline="", encoding="utf-8") as results_file:
        writer = csv.writer(results_file)
        writer.writerow(columns)
        writer.writerows(rows)


def test_model_analytics_reports_missing_artifacts(app, admin_client, tmp_path):
    app.config["YOLO_METRICS_DIR"] = str(tmp_path)

    response = admin_client.get("/api/admin/model-analytics")

    assert response.status_code == 200
    assert response.get_json()["metrics"] is None
    assert response.get_json()["confusion_matrix"] is None
    assert response.get_json()["missing"] == ["results.csv", "confusion_matrix.csv"]


def test_model_analytics_uses_exported_yolo_values(app, admin_client, tmp_path):
    app.config["YOLO_METRICS_DIR"] = str(tmp_path)
    _write_results(tmp_path / "results.csv")
    with open(tmp_path / "confusion_matrix.csv", "w", newline="", encoding="utf-8") as matrix_file:
        writer = csv.writer(matrix_file)
        writer.writerows([
            ["actual/predicted", "plastic", "background"],
            ["plastic", 7, 1],
            ["background", 2, 0],
        ])

    response = admin_client.get("/api/admin/model-analytics")
    data = response.get_json()

    assert response.status_code == 200
    assert data["metrics"]["epochs"] == [1, 2]
    assert data["metrics"]["map50"] == [0.4, 0.6]
    assert data["metrics"]["train_loss"] == [4, 2]
    assert data["metrics"]["val_loss"] == [6, 4]
    assert data["metrics"]["loss_reduction_percent"] == [0, 50]
    assert data["confusion_matrix"]["labels"] == ["plastic", "background"]
    assert data["confusion_matrix"]["values"] == [[7, 1], [2, 0]]
    assert data["missing"] == []
