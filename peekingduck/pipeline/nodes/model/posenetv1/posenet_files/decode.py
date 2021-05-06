"""
Copyright 2018 Ross Wightman
Modifications copyright 2021 AI Singapore

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
from typing import List
import numpy as np

from peekingduck.pipeline.nodes.model.posenetv1.posenet_files.constants import POSE_CONNECTIONS


def decode_pose(root_score: float,
                root_id: int,
                root_image_coord: List[float],
                scores: List[List[List[float]]],
                offsets: List[List[List[List[float]]]],
                output_stride: int,
                displacements_fwd: List[List[List[List[float]]]],
                displacements_bwd: List[List[List[List[float]]]],
                keypoint_scores: List[float],
                keypoint_coords: List[List[float]]):
    """ Decode pose's keypoints scores and coordinates from keypoints score,
    coordinates and displancements

    Args:
        root_score (float): a keypoint with highest score is selected as root
        root_id (int): root keypoint's index
        root_image_coord (np.array): relative coordinate of root keypoint
        scores (np.array): (h x w x num_parts) heatmap scores of body parts
        offsets (np.array): (h x w x num_parts x 2) short range offset vector of body parts
        output_stride (int): output stride to convert output indices to image coordinates
        displacements_fwd (np.array): (h x w x num_edges x 2) forward displacements
                of body connections
        displacements_bwd (np.array): (h x w x num_edges x 2) backward displacements
                of body connections
        keypoints_scores (np.array): 17x1 buffer to store keypoint scores
        keypoint_coords (np.array): 17x2 buffer to store keypoint coordinates

    Returns:
        pose_count (int): number of poses detected
    """
    num_edges = len(POSE_CONNECTIONS)

    keypoint_scores[root_id] = root_score
    keypoint_coords[root_id] = root_image_coord

    for edge in reversed(range(num_edges)):
        target_keypoint_id, source_keypoint_id = POSE_CONNECTIONS[edge]
        _calculate_instance_keypoints(edge,
                                      target_keypoint_id,
                                      source_keypoint_id,
                                      keypoint_scores,
                                      keypoint_coords,
                                      scores,
                                      offsets,
                                      output_stride,
                                      displacements_bwd)

    for edge in range(num_edges):
        source_keypoint_id, target_keypoint_id = POSE_CONNECTIONS[edge]
        _calculate_instance_keypoints(edge,
                                      target_keypoint_id,
                                      source_keypoint_id,
                                      keypoint_scores,
                                      keypoint_coords,
                                      scores,
                                      offsets,
                                      output_stride,
                                      displacements_fwd)


def _calculate_instance_keypoints(edge: int,
                                  target_keypoint_id: int,
                                  source_keypoint_id: int,
                                  instance_keypoint_scores: List[float],
                                  instance_keypoint_coords: List[List[float]],
                                  scores: List[List[List[float]]],
                                  offsets: List[List[List[List[float]]]],
                                  output_stride: int,
                                  displacements: List[List[List[List[float]]]]):
    if (instance_keypoint_scores[source_keypoint_id] > 0.0 and
            instance_keypoint_scores[target_keypoint_id] == 0.0):
        source_keypoint = instance_keypoint_coords[source_keypoint_id]

        score, coords = _traverse_to_target_keypoint(edge,
                                                     source_keypoint,
                                                     target_keypoint_id,
                                                     scores,
                                                     offsets,
                                                     output_stride,
                                                     displacements)

        instance_keypoint_scores[target_keypoint_id] = score
        instance_keypoint_coords[target_keypoint_id] = coords


def _clip_to_indices(keypoints: List[float],
                     output_stride: int,
                     width: int,
                     height: int):
    """Clip keypoint coordinate to indices within dimension (width, height)"""
    keypoints = keypoints / output_stride
    keypoint_indices = np.zeros((2,), dtype=np.int32)

    keypoint_indices[0] = max(min(round(keypoints[0]), width - 1), 0)
    keypoint_indices[1] = max(min(round(keypoints[1]), height - 1), 0)

    return keypoint_indices


def _traverse_to_target_keypoint(edge_id: int,
                                 source_keypoint: int,
                                 target_keypoint_id: int,
                                 scores: List[float],
                                 offsets: List[List[List[List[float]]]],
                                 output_stride: int,
                                 displacements: List[List[List[List[float]]]]):
    height = scores.shape[0] - 1
    width = scores.shape[1] - 1

    source_keypoint_indices = _clip_to_indices(
        source_keypoint, output_stride, width, height)

    displaced_point = source_keypoint + displacements[
        source_keypoint_indices[1], source_keypoint_indices[0], edge_id]

    displaced_point_indices = _clip_to_indices(
        displaced_point, output_stride, width, height)

    score = scores[displaced_point_indices[1],
                   displaced_point_indices[0], target_keypoint_id]

    image_coord = displaced_point_indices * output_stride + offsets[
        displaced_point_indices[1], displaced_point_indices[0], target_keypoint_id]

    return score, image_coord
