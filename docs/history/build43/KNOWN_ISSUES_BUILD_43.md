# Build 43 limitations and pending work

- Requires acceptance on your Android devices with your Maps/Places configuration, staging URL and signing keys. Compilation does not verify real GPS, map gestures, keyboard resizing, large text or OEM background behavior.
- No deployment, live Render performance measurement or real Stripe provider interaction was performed here. Existing test-provider configuration remains required. Payment regression uses a fake provider; a staging trip payment record is not proof of a Stripe capture.
- Waiting/no-show is fleet/shared-backend only. It intentionally charges zero and adds no earnings/bonus. No rider contact attempt is performed or asserted. GPS is verified at arrival and cancellation, not continuously along the five-minute interval. Passenger countdown uses the device clock for display; only the server authorizes cancellation.
- The new terminal status requires both apps updated as described in START_HERE. Cancellations appear in Passenger/Admin; Driver completed-trip earnings history still lists completed paid-demo trips, not all cancellations.
- Search needs configured Google Places and a network connection. Address lookup may fail; the selected coordinates and an explicit pin label remain available. A map pin does not verify curb access, safety or legal stopping conditions.
- Manual pickup enables choosing a different meeting point. A dedicated "book for another rider" identity/contact/consent flow is not implemented.
- Signup still follows invited-staging access. Real SMS, live charges/payouts, in-app calling/messaging and launch approval remain gated.
- The original roadmap's Share Trip, emergency-contact improvements and Driver boost-zone map are **not implemented by this Build 43**. Existing server boost rules remain. Their scheduling must be agreed alongside dependencies and testing; they are not silently marked complete.
- Compilation retains existing deprecated Compose icon/API warnings. They are not compile errors; migration can follow separately.
