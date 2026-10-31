"""Dataset splitting specifications ensuring seed disjointness and parameter range holdouts."""

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple
from netcoop.data.generator import NoiseShape, SeverityLevel


@dataclass(frozen=True)
class SplitSpec:
    """Specification for a single dataset split partition."""

    name: str
    seed_start: int
    seed_end: int
    severities: Tuple[SeverityLevel, ...]
    noise_shapes: Tuple[NoiseShape, ...]
    missing_rate_range: Tuple[float, float]
    onset_offset_range: Tuple[float, float]

    @property
    def seeds(self) -> Set[int]:
        """Set of discrete pseudo-random integer seeds in this split."""
        return set(range(self.seed_start, self.seed_end + 1))


class DatasetSplitter:
    """Manages strictly non-overlapping train, calibration, validation, and test splits."""

    # Explicit seed boundaries (minimum 300 runs across classes)
    TRAIN_SPEC = SplitSpec(
        name="train",
        seed_start=1,
        seed_end=200,
        severities=(SeverityLevel.LOW, SeverityLevel.MEDIUM),
        noise_shapes=(NoiseShape.GAUSSIAN, NoiseShape.UNIFORM),
        missing_rate_range=(0.0, 0.2),
        onset_offset_range=(0.0, 60.0),
    )

    CALIBRATION_SPEC = SplitSpec(
        name="calibration",
        seed_start=201,
        seed_end=250,
        severities=(SeverityLevel.LOW, SeverityLevel.MEDIUM),
        noise_shapes=(NoiseShape.GAUSSIAN, NoiseShape.UNIFORM),
        missing_rate_range=(0.0, 0.2),
        onset_offset_range=(0.0, 60.0),
    )

    VALIDATION_SPEC = SplitSpec(
        name="validation",
        seed_start=251,
        seed_end=300,
        severities=(SeverityLevel.HIGH,),
        noise_shapes=(NoiseShape.GAUSSIAN, NoiseShape.UNIFORM, NoiseShape.BURST),
        missing_rate_range=(0.1, 0.4),
        onset_offset_range=(30.0, 120.0),
    )

    TEST_SPEC = SplitSpec(
        name="test",
        seed_start=301,
        seed_end=360,
        severities=(SeverityLevel.HIGH, SeverityLevel.CRITICAL),
        noise_shapes=(NoiseShape.BURST, NoiseShape.GAUSSIAN),
        missing_rate_range=(0.2, 0.6),
        onset_offset_range=(60.0, 180.0),
    )

    @classmethod
    def verify_no_seed_overlap(cls) -> None:
        """Assert that no seed is shared between any partitions."""
        train_s = cls.TRAIN_SPEC.seeds
        calib_s = cls.CALIBRATION_SPEC.seeds
        val_s = cls.VALIDATION_SPEC.seeds
        test_s = cls.TEST_SPEC.seeds

        assert len(train_s & calib_s) == 0, f"Overlap between train and calib: {train_s & calib_s}"
        assert len(train_s & val_s) == 0, f"Overlap between train and val: {train_s & val_s}"
        assert len(train_s & test_s) == 0, f"Overlap between train and test: {train_s & test_s}"
        assert len(calib_s & val_s) == 0, f"Overlap between calib and val: {calib_s & val_s}"
        assert len(calib_s & test_s) == 0, f"Overlap between calib and test: {calib_s & test_s}"
        assert len(val_s & test_s) == 0, f"Overlap between val and test: {val_s & test_s}"

    @classmethod
    def get_split_spec(cls, split_name: str) -> SplitSpec:
        """Retrieve partition specification by name."""
        cls.verify_no_seed_overlap()
        specs = {
            "train": cls.TRAIN_SPEC,
            "calibration": cls.CALIBRATION_SPEC,
            "validation": cls.VALIDATION_SPEC,
            "test": cls.TEST_SPEC,
        }
        if split_name not in specs:
            raise ValueError(f"Unknown split name '{split_name}'. Choose from: {list(specs.keys())}")
        return specs[split_name]


# Enforce verification on module import
DatasetSplitter.verify_no_seed_overlap()
