from app.models.booking import (
    AssistantConversation,
    AssistantMessage,
    Booking,
    Hotel,
    Notification,
    NotificationDelivery,
    Payment,
    RoomInventory,
    RoomType,
)
from app.models.catalog import Attraction, AttractionCategory, Destination, destination_categories
from app.models.itinerary import Itinerary, ItineraryActivity, ItineraryVersion
from app.models.optimization import AdaptationProposal, ContextSnapshot, OptimizationRun
from app.models.recommendations import (
    RecommendationFeedback,
    RecommendationItem,
    RecommendationRun,
    UserInteraction,
)
from app.models.user import AuditLog, RefreshToken, Role, User, UserPreference

__all__ = [
    "AssistantConversation", "AssistantMessage", "Booking", "Hotel", "Notification", "NotificationDelivery", "Payment",
    "RoomInventory", "RoomType",
    "AdaptationProposal", "ContextSnapshot", "OptimizationRun",
    "Itinerary", "ItineraryActivity", "ItineraryVersion",
    "RecommendationFeedback", "RecommendationItem", "RecommendationRun", "UserInteraction",
    "Attraction", "AttractionCategory", "AuditLog", "Destination", "RefreshToken", "Role",
    "User", "UserPreference", "destination_categories",
]
