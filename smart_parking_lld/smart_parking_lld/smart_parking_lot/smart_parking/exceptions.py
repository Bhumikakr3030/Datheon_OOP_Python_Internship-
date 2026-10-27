"""Domain-specific exceptions."""


class ParkingError(Exception):
    """Base class for all parking-lot errors."""


class ParkingFullError(ParkingError):
    """No compatible slot is available for the vehicle."""


class DuplicateVehicleError(ParkingError):
    """The vehicle is already parked inside the lot."""


class InvalidTicketError(ParkingError):
    """Ticket is unknown or already closed."""
