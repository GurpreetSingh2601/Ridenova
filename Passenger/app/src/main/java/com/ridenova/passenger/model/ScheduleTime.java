package com.ridenova.passenger.model;

import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Locale;

/** Pure date/time logic, also tested on a standard JDK without Android. */
public final class ScheduleTime {
    private ScheduleTime() {}

    public static long resolve(int year, int month, int day, int hour, int minute, String zoneId) {
        LocalDateTime local = LocalDateTime.of(year, month, day, hour, minute);
        ZoneId zone = ZoneId.of(zoneId);
        List<ZoneOffset> offsets = zone.getRules().getValidOffsets(local);
        if (offsets.isEmpty()) {
            throw new IllegalArgumentException("That time does not exist because the clock changes. Choose another time.");
        }
        if (offsets.size() != 1) {
            throw new IllegalArgumentException("That time occurs twice because the clock changes. Choose an unambiguous time.");
        }
        return local.toInstant(offsets.get(0)).toEpochMilli();
    }

    public static boolean isBookable(long pickupMillis, long nowMillis) {
        return pickupMillis >= nowMillis + 15 * 60_000L && pickupMillis <= nowMillis + 30 * 86_400_000L;
    }

    public static String label(long millis, String zoneId) {
        return DateTimeFormatter.ofPattern("EEE, d MMM yyyy · h:mm a z", Locale.getDefault())
            .format(Instant.ofEpochMilli(millis).atZone(ZoneId.of(zoneId)));
    }
}
