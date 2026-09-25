import com.ridenova.passenger.model.ScheduleTime;
import java.time.Instant;

public class ScheduleTimeTest {
    private static void check(boolean value) {
        if (!value) throw new AssertionError();
    }
    private static void rejects(Runnable action) {
        try { action.run(); } catch (IllegalArgumentException expected) { return; }
        throw new AssertionError("Expected invalid local time to be rejected");
    }
    public static void main(String[] args) {
        long now = Instant.parse("2026-01-01T00:00:00Z").toEpochMilli();
        check(ScheduleTime.isBookable(now + 900000, now));
        check(!ScheduleTime.isBookable(now + 899999, now));
        check(ScheduleTime.isBookable(now + 30 * 86400000L, now));
        check(!ScheduleTime.isBookable(now + 30 * 86400000L + 1, now));
        long utc = ScheduleTime.resolve(2026, 1, 1, 8, 0, "UTC");
        check(utc == Instant.parse("2026-01-01T08:00:00Z").toEpochMilli());
        check(ScheduleTime.resolve(2026, 1, 1, 0, 0, "America/Vancouver") == utc);
        // Use New York to test DST without assuming BC's future clock policy.
        rejects(() -> ScheduleTime.resolve(2025, 3, 9, 2, 30, "America/New_York"));
        rejects(() -> ScheduleTime.resolve(2025, 11, 2, 1, 30, "America/New_York"));
        check(ScheduleTime.label(utc, "UTC").contains("2026"));
        System.out.println("9 scheduling date/time checks passed");
    }
}
