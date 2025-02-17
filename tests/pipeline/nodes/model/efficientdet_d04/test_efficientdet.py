"""
Copyright 2021 AI Singapore

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from pathlib import Path

import cv2
import numpy as np
import numpy.testing as npt
import pytest
import yaml

from peekingduck.pipeline.nodes.model.efficientdet import Node
from peekingduck.pipeline.nodes.model.efficientdet_d04.efficientdet_files.detector import (
    Detector,
)
from peekingduck.pipeline.nodes.model.efficientdet_d04.efficientdet_files.model import (
    efficientdet as edet,
)


@pytest.fixture
def efficientdet_config():
    filepath = (
        Path.cwd()
        / "tests"
        / "pipeline"
        / "nodes"
        / "model"
        / "efficientdet_d04"
        / "test_efficientdet.yml"
    )

    with open(filepath) as file:
        node_config = yaml.safe_load(file)
    node_config["root"] = Path.cwd()

    return node_config


@pytest.fixture
def model_dir(efficientdet_config):
    return (
        efficientdet_config["root"].parent
        / "peekingduck_weights"
        / efficientdet_config["weights"]["model_subdir"]
    )


@pytest.fixture(params=[0, 1, 2, 3, 4])
def efficientdet(request, efficientdet_config):
    efficientdet_config["model_type"] = request.param
    node = Node(efficientdet_config)

    return node


@pytest.fixture()
def efficientdet_detector(efficientdet_config, model_dir):
    efficientdet_config["model_type"] = 0
    detector = Detector(efficientdet_config, model_dir)

    return detector


@pytest.mark.mlmodel
class TestEfficientDet:
    def test_no_human_image(self, test_no_human_images, efficientdet):
        blank_image = cv2.imread(test_no_human_images)
        output = efficientdet.run({"img": blank_image})
        expected_output = {
            "bboxes": np.empty((0, 4), dtype=np.float32),
            "bbox_labels": np.empty((0)),
            "bbox_scores": np.empty((0), dtype=np.float32),
        }
        assert output.keys() == expected_output.keys()
        npt.assert_equal(output["bboxes"], expected_output["bboxes"])
        npt.assert_equal(output["bbox_labels"], expected_output["bbox_labels"])
        npt.assert_equal(output["bbox_scores"], expected_output["bbox_scores"])

    def test_return_at_least_one_person_and_one_bbox(
        self, test_human_images, efficientdet
    ):
        test_img = cv2.imread(test_human_images)
        output = efficientdet.run({"img": test_img})
        assert "bboxes" in output
        assert "bbox_labels" in output
        assert "bbox_scores" in output
        assert output["bboxes"].size != 0
        assert output["bbox_labels"].size != 0
        assert output["bbox_scores"].size != 0

    def test_efficientdet_preprocess(self, create_image, efficientdet_detector):
        test_img1 = create_image((720, 1280, 3))
        test_img2 = create_image((640, 480, 3))
        actual_img1, actual_scale1 = efficientdet_detector.preprocess(test_img1, 512)
        actual_img2, actual_scale2 = efficientdet_detector.preprocess(test_img2, 512)

        assert actual_img1.shape == (512, 512, 3)
        assert actual_img2.shape == (512, 512, 3)
        assert actual_img1.dtype == np.float32
        assert actual_img2.dtype == np.float32
        assert actual_scale1 == 0.4
        assert actual_scale2 == 0.8

    def test_efficientdet_postprocess(self, efficientdet_detector):
        output_bbox = np.array([[1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0]])
        output_label = np.array([0, 0])
        output_score = np.array([0.9, 0.2])
        network_output = (output_bbox, output_score, output_label)
        scale = 0.5
        img_shape = (720, 1280)
        detect_ids = [0]
        boxes, labels, scores = efficientdet_detector.postprocess(
            network_output, scale, img_shape, detect_ids
        )

        expected_bbox = np.array([[1, 2, 3, 4]]) / scale
        expected_bbox[:, [0, 2]] /= img_shape[1]
        expected_bbox[:, [1, 3]] /= img_shape[0]

        expected_score = np.array([0.9])
        npt.assert_almost_equal(expected_bbox, boxes)
        npt.assert_almost_equal(expected_score, scores)
        npt.assert_equal(np.array(["person"]), labels)

    def test_efficientdet_model_initializations(self):
        test_models = {}
        test_models["normal"] = edet(1)
        test_models["weighted"] = edet(1, weighted_bifpn=False)
        test_models["detect_quadrangle"] = edet(1, detect_quadrangle=True)
        test_models["no_sepearable_conv"] = edet(1, separable_conv=False)

        for key in test_models:
            assert test_models[key] is not None
