from typing import NewType

# Base ID 
ID = NewType("ID", int)

# Core domain IDs 
EventID = NewType("EventID", int)
OccurrenceID = NewType("OccurrenceID", int)
TourID = NewType("TourID", int)

# Participants 
ParticipantID = NewType("ParticipantID", int)
ArtistID = NewType("ArtistID", int)
GroupID = NewType("GroupID", int)
OrganizerID = NewType("OrganizerID", int)

# Location 
VenueID = NewType("VenueID", int)
CityID = NewType("CityID", int)
CountryID = NewType("CountryID", int)

# Tickets 
TicketOfferID = NewType("TicketOfferID", int)
PromoCodeID = NewType("PromoCodeID", int)
PriceHistoryEntryID = NewType("PriceHistoryEntryID", int)

