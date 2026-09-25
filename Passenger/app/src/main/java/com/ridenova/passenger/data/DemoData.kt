package com.ridenova.passenger.data

import com.ridenova.passenger.model.PlaceSuggestion
import com.ridenova.passenger.model.RideOption
import com.ridenova.passenger.model.RideTier

object DemoData {
    val places = listOf(
        PlaceSuggestion("Vancouver International Airport (YVR)", "3211 Grant McConachie Way, Richmond, BC", 49.1951, -123.1779),
        PlaceSuggestion("Metropolis at Metrotown", "4700 Kingsway, Burnaby, BC", 49.2261, -123.0025),
        PlaceSuggestion("Canada Place", "999 Canada Pl, Vancouver, BC", 49.2888, -123.1111),
        PlaceSuggestion("Stanley Park", "Vancouver, BC", 49.3043, -123.1443),
        PlaceSuggestion("Surrey Central Station", "10277 City Pkwy, Surrey, BC", 49.1896, -122.8480)
    )

    val rideOptions = listOf(
        RideOption(RideTier.ECONOMY, "Economy", "Affordable everyday rides", 3, 18.40, 4),
        RideOption(RideTier.COMFORT, "Comfort", "Newer, roomier vehicles", 5, 24.70, 4),
        RideOption(RideTier.XL, "XL", "Up to 6 passengers", 7, 31.20, 6)
    )
}
