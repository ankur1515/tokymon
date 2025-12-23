"""Session modules for Tokymon POC activities."""
from __future__ import annotations

from sessions.modules.base import BaseModule
from sessions.modules.object_identification import ObjectIdentificationModule
from sessions.modules.environment_orientation import EnvironmentOrientationModule
from sessions.modules.emotion_affect import EmotionAffectModule
from sessions.modules.body_movement import BodyMovementModule
from sessions.modules.joint_attention import JointAttentionModule
from sessions.modules.obstacle_course import ObstacleCourseModule
from sessions.modules.academic_foundation import AcademicFoundationModule
from sessions.modules.sensory_response import SensoryResponseModule
from sessions.modules.parent_collaboration import ParentCollaborationModule
from sessions.modules.basic_commands import BasicCommandsModule

__all__ = [
    "BaseModule",
    "ObjectIdentificationModule",
    "EnvironmentOrientationModule",
    "EmotionAffectModule",
    "BodyMovementModule",
    "JointAttentionModule",
    "ObstacleCourseModule",
    "AcademicFoundationModule",
    "SensoryResponseModule",
    "ParentCollaborationModule",
    "BasicCommandsModule",
]

# Module registry in execution order
MODULE_REGISTRY = [
    ("object_identification", ObjectIdentificationModule),
    ("environment_orientation", EnvironmentOrientationModule),
    ("emotion_affect", EmotionAffectModule),
    ("body_movement", BodyMovementModule),
    ("joint_attention", JointAttentionModule),
    ("obstacle_course", ObstacleCourseModule),
    ("academic_foundation", AcademicFoundationModule),
    ("sensory_response", SensoryResponseModule),
    ("parent_collaboration", ParentCollaborationModule),
    ("basic_commands", BasicCommandsModule),
]

