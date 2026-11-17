"""Immutable public records and exact JSON codecs."""
from dataclasses import dataclass
from fractions import Fraction
import json
import re

def rational(value):
    if isinstance(value, bool):
        raise ValueError("boolean is not a rational")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, str) and re.fullmatch(r"-?\d+(?:/[1-9]\d*)?", value):
        return Fraction(value)
    raise ValueError("expected integer, Fraction, or integer/rational string")

def identifier(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("ID must be a nonempty string")
    return value

def integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError("invalid integer")
    return value

@dataclass(frozen=True)
class Observation:
    subject: str
    segment: str
    revision: int
    weight: Fraction
    enter: Fraction
    exit: Fraction
    event: int

    def __post_init__(self):
        identifier(self.subject)
        identifier(self.segment)
        integer(self.revision, 1)
        for name in ("weight", "enter", "exit"):
            object.__setattr__(self, name, rational(getattr(self, name)))
        if self.weight <= 0 or self.enter >= self.exit:
            raise ValueError("positive weight and enter < exit required")
        if type(self.event) is not int or self.event not in (0, 1, 2):
            raise ValueError("event must be 0, 1, or 2")

    @classmethod
    def from_record(cls, row):
        if not isinstance(row, dict) or set(row) != {
            "subject", "segment", "revision", "weight", "enter", "exit", "event"
        }:
            raise ValueError("invalid observation fields")
        return cls(**row)

    def record(self):
        return dict(subject=self.subject, segment=self.segment,
                    revision=self.revision, weight=str(self.weight),
                    enter=str(self.enter), exit=str(self.exit), event=self.event)

@dataclass(frozen=True)
class Receipt:
    epoch: int
    changed: tuple[str, ...]

@dataclass(frozen=True)
class Cohort:
    id: str
    source_epoch: int
    observations: tuple[Observation, ...]
    times: tuple[Fraction, ...]
    causes: tuple[int, ...]

@dataclass(frozen=True)
class Report:
    id: str
    cohort_id: str
    source_epoch: int
    coordinates: tuple[tuple[Fraction, int], ...]
    survival: tuple[Fraction, ...]
    probabilities: tuple[Fraction, ...]
    covariance: tuple[tuple[Fraction, ...], ...]

    def record(self):
        return dict(id=self.id, cohort_id=self.cohort_id,
                    source_epoch=self.source_epoch,
                    coordinates=[[str(t), c] for t, c in self.coordinates],
                    survival=[str(x) for x in self.survival],
                    probabilities=[str(x) for x in self.probabilities],
                    covariance=[[str(x) for x in row] for row in self.covariance])

def dumps(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def cohort_record(cohort):
    return dict(id=cohort.id, source_epoch=cohort.source_epoch,
                observations=[x.record() for x in cohort.observations],
                times=[str(t) for t in cohort.times], causes=list(cohort.causes))

def cohort_from_record(row):
    return Cohort(row["id"], row["source_epoch"],
                  tuple(Observation.from_record(x) for x in row["observations"]),
                  tuple(rational(t) for t in row["times"]), tuple(row["causes"]))

def report_from_record(row):
    return Report(row["id"], row["cohort_id"], row["source_epoch"],
                  tuple((rational(t), c) for t, c in row["coordinates"]),
                  tuple(map(rational, row["survival"])),
                  tuple(map(rational, row["probabilities"])),
                  tuple(tuple(map(rational, xs)) for xs in row["covariance"]))
