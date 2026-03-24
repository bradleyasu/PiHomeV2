"""
insight.py

A Python class representing a Tomorrow.io severe weather insight event,
parsed from the Events API response payload.

Usage:
    # From a single event dict
    event = Insight(event_dict)

    # From a full API response (returns a list of Insight objects)
    insights = Insight.from_response(api_response)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import json


# ---------------------------------------------------------------------------
# Enums (as string constants for easy serialisation / comparison)
# ---------------------------------------------------------------------------

class Severity:
    EXTREME  = "extreme"
    SEVERE   = "severe"
    MODERATE = "moderate"
    MINOR    = "minor"
    UNKNOWN  = "unknown"

    ALL = {EXTREME, SEVERE, MODERATE, MINOR, UNKNOWN}
    RANK = {EXTREME: 4, SEVERE: 3, MODERATE: 2, MINOR: 1, UNKNOWN: 0}


class Certainty:
    OBSERVED = "observed"
    LIKELY   = "likely"
    POSSIBLE = "possible"
    UNLIKELY = "unlikely"
    UNKNOWN  = "unknown"


class Urgency:
    IMMEDIATE = "immediate"
    EXPECTED  = "expected"
    FUTURE    = "future"
    PAST      = "past"
    UNKNOWN   = "unknown"


# ---------------------------------------------------------------------------
# EventValues – the nested eventValues / triggerValues object
# ---------------------------------------------------------------------------

@dataclass
class EventValues:
    title:       Optional[str] = None
    origin:      Optional[str] = None
    location:    Optional[dict] = None   # GeoJSON geometry
    geocodes:    list[str]      = field(default_factory=list)
    distance:    Optional[float] = None  # km from queried location
    direction:   Optional[float] = None  # degrees CCW from due north
    description: Optional[str]  = None
    instruction: Optional[str]  = None

    # Catch-all for any extra / beta fields returned by the API
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "EventValues":
        known = {"title", "origin", "location", "geocodes",
                 "distance", "direction", "description", "instruction"}
        return cls(
            title       = data.get("title"),
            origin      = data.get("origin"),
            location    = data.get("location"),
            geocodes    = data.get("geocodes", []),
            distance    = data.get("distance"),
            direction   = data.get("direction"),
            description = data.get("description"),
            instruction = data.get("instruction"),
            extra       = {k: v for k, v in data.items() if k not in known},
        )

    def to_dict(self) -> dict:
        d = {
            "title":       self.title,
            "origin":      self.origin,
            "location":    self.location,
            "geocodes":    self.geocodes,
            "distance":    self.distance,
            "direction":   self.direction,
            "description": self.description,
            "instruction": self.instruction,
        }
        d.update(self.extra)
        return {k: v for k, v in d.items() if v is not None}


# ---------------------------------------------------------------------------
# Main Insight class
# ---------------------------------------------------------------------------

@dataclass
class Insight:
    """
    Represents a single Tomorrow.io severe weather event/insight.

    Attributes mirror the Events API event object as documented at
    https://docs.tomorrow.io/reference/events-overview
    """

    # Core identity
    insight:       str                   # e.g. "winter", "wind", "floods"
    severity:      str = Severity.UNKNOWN
    certainty:     str = Certainty.UNKNOWN
    urgency:       str = Urgency.UNKNOWN

    # Timestamps (UTC-aware datetime objects, or None if absent)
    start_time:  Optional[datetime] = None
    end_time:    Optional[datetime] = None
    update_time: Optional[datetime] = None

    # Nested value objects
    event_values:   EventValues = field(default_factory=EventValues)
    trigger_values: EventValues = field(default_factory=EventValues)

    # Catch-all for any top-level fields not explicitly mapped
    raw: dict = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict) -> "Insight":
        """Build an Insight from a single event dict."""
        return cls(
            insight       = data.get("insight", "unknown"),
            severity      = data.get("severity", Severity.UNKNOWN),
            certainty     = data.get("certainty", Certainty.UNKNOWN),
            urgency       = data.get("urgency", Urgency.UNKNOWN),
            start_time    = _parse_dt(data.get("startTime")),
            end_time      = _parse_dt(data.get("endTime")),
            update_time   = _parse_dt(data.get("updateTime")),
            event_values  = EventValues.from_dict(data.get("eventValues") or {}),
            trigger_values= EventValues.from_dict(data.get("triggerValues") or {}),
            raw           = data,
        )

    @classmethod
    def from_response(cls, response: dict) -> list["Insight"]:
        """
        Parse a full API response payload and return a list of Insight objects.

        Handles both:
          { "events": [ ... ] }          <- Events API
          { "data": { "events": [...] }} <- some wrapped response shapes
        """
        events = (
            response.get("events")
            or response.get("data", {}).get("events")
            or []
        )
        return [cls.from_dict(e) for e in events]

    @classmethod
    def from_json(cls, json_str: str) -> list["Insight"]:
        """Parse a JSON string of a full API response."""
        return cls.from_response(json.loads(json_str))

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def title(self) -> Optional[str]:
        """Short human-readable event title (e.g. 'Winter Storm Warning')."""
        return self.event_values.title

    @property
    def description(self) -> Optional[str]:
        """Extended human-readable description of the hazard."""
        return self.event_values.description

    @property
    def instruction(self) -> Optional[str]:
        """Extended human-readable action instructions."""
        return self.event_values.instruction

    @property
    def origin(self) -> Optional[str]:
        """Source of the event (e.g. 'NWS')."""
        return self.event_values.origin

    @property
    def location(self) -> Optional[dict]:
        """GeoJSON geometry of the affected area."""
        return self.event_values.location

    @property
    def distance_km(self) -> Optional[float]:
        """Distance in km from the queried location."""
        return self.event_values.distance

    @property
    def severity_rank(self) -> int:
        """Numeric rank for sorting: extreme=4, severe=3, moderate=2, minor=1, unknown=0."""
        return Severity.RANK.get(self.severity, 0)

    @property
    def is_active(self) -> bool:
        """True if the event is currently ongoing (now falls within start–end window)."""
        now = datetime.now(timezone.utc)
        if self.start_time and self.end_time:
            return self.start_time <= now <= self.end_time
        return False

    @property
    def is_upcoming(self) -> bool:
        """True if the event has not yet started."""
        now = datetime.now(timezone.utc)
        return bool(self.start_time and now < self.start_time)

    @property
    def is_past(self) -> bool:
        """True if the event has already ended."""
        now = datetime.now(timezone.utc)
        return bool(self.end_time and now > self.end_time)

    @property
    def duration_hours(self) -> Optional[float]:
        """Duration of the event in hours, or None if times are unavailable."""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return round(delta.total_seconds() / 3600, 2)
        return None

    # ------------------------------------------------------------------
    # Filtering helpers (useful when working with a list of Insights)
    # ------------------------------------------------------------------

    @staticmethod
    def filter_by_category(insights: list["Insight"], category: str) -> list["Insight"]:
        """Return only insights matching a given category (e.g. 'winter')."""
        return [i for i in insights if i.insight.lower() == category.lower()]

    @staticmethod
    def filter_by_severity(insights: list["Insight"], min_severity: str) -> list["Insight"]:
        """
        Return insights at or above the given severity level.
        min_severity should be one of: 'minor', 'moderate', 'severe', 'extreme'.
        """
        min_rank = Severity.RANK.get(min_severity, 0)
        return [i for i in insights if i.severity_rank >= min_rank]

    @staticmethod
    def filter_active(insights: list["Insight"]) -> list["Insight"]:
        """Return only currently active insights."""
        return [i for i in insights if i.is_active]

    @staticmethod
    def filter_upcoming(insights: list["Insight"]) -> list["Insight"]:
        """Return only upcoming (not yet started) insights."""
        return [i for i in insights if i.is_upcoming]

    @staticmethod
    def sort_by_severity(insights: list["Insight"], descending: bool = True) -> list["Insight"]:
        """Sort a list of insights by severity rank."""
        return sorted(insights, key=lambda i: i.severity_rank, reverse=descending)

    @staticmethod
    def sort_by_start_time(insights: list["Insight"], descending: bool = False) -> list["Insight"]:
        """Sort a list of insights by start time (ascending by default)."""
        return sorted(
            insights,
            key=lambda i: i.start_time or datetime.min.replace(tzinfo=timezone.utc),
            reverse=descending,
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a clean dict representation of this insight."""
        return {
            "insight":       self.insight,
            "severity":      self.severity,
            "certainty":     self.certainty,
            "urgency":       self.urgency,
            "startTime":     self.start_time.isoformat() if self.start_time else None,
            "endTime":       self.end_time.isoformat()   if self.end_time   else None,
            "updateTime":    self.update_time.isoformat() if self.update_time else None,
            "eventValues":   self.event_values.to_dict(),
            "triggerValues": self.trigger_values.to_dict(),
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialise this insight to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Return a concise one-line human-readable summary."""
        parts = [
            f"[{self.insight.upper()}]",
            self.title or "(no title)",
            f"| severity={self.severity}",
            f"| certainty={self.certainty}",
            f"| urgency={self.urgency}",
        ]
        if self.start_time:
            parts.append(f"| starts={self.start_time.strftime('%Y-%m-%d %H:%M UTC')}")
        if self.end_time:
            parts.append(f"| ends={self.end_time.strftime('%Y-%m-%d %H:%M UTC')}")
        return " ".join(parts)

    def __repr__(self) -> str:
        return (
            f"Insight(insight={self.insight!r}, title={self.title!r}, "
            f"severity={self.severity!r}, active={self.is_active})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Insight):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __lt__(self, other: "Insight") -> bool:
        """Enables sorting by severity rank (ascending)."""
        return self.severity_rank < other.severity_rank


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO 8601 string into a UTC-aware datetime, or return None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None