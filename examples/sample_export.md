# Exported Chat — BioPrism Auth Refactor
Exported: 2025-03-14

---

**User:** Hey, let's continue working on the BioPrism desktop app. We need to add a trial license system so users have a 14-day free trial before they need to buy.

**Claude:** Sure. I'd suggest storing a trial start date in a local file at `~/.bioprism/trial.json` and checking it at app startup. We can use a simple JSON file with `start_date` and `machine_id` fields. The machine ID prevents easy resets by deleting the file.

**User:** Let's do it. Also the app needs to use SQLite to store activation keys — we looked at using a plain text file before but that was too easy to bypass.

**Claude:** Good call on SQLite over plain text. Here's the plan:
- `trial_manager.py` handles trial logic
- SQLite DB at `~/.bioprism/license.db`
- Table: `activations(machine_id TEXT, key TEXT, activated_at TEXT, expires_at TEXT)`
- Machine ID generated from MAC address + hostname hash

**User:** Wait, I tried using MAC address for machine ID last week and it broke on VMs because the MAC is randomized. Wasted about 3 hours debugging that.

**Claude:** Good catch. We should use a combination of hostname + CPU serial + OS install date instead. More stable across environments.

**User:** Yeah let's use that. Also I tried salting the activation keys with SHA256 but the salt ended up in the binary and someone extracted it with strings command. Don't do that again.

**Claude:** Noted. We'll use HMAC-SHA256 with a server-side secret instead. The key validation will hit our API endpoint rather than doing client-side crypto. Endpoint: `https://api.bioprism.io/v1/validate`.

**User:** Perfect. Also let's pin the API version to v1 forever — we can't break existing installations.

**Claude:** Agreed. I'll add that as a constant: `API_VERSION = "v1"`. Won't change without explicit migration plan.

**User:** What's the status of the trial UI? I thought we were going to show a banner.

**Claude:** Not done yet. The plan is to show a banner in the main window title bar showing "Trial: X days remaining". Still open — we haven't implemented it.

**User:** OK. Also I tried using `tkinter.messagebox` for the expiry dialog but it blocked the main thread and froze the whole app. Spent about 2 hours on that.

**Claude:** Right, we need to run that dialog in a separate thread or use `app.after()` scheduling. I'll use `app.after(0, show_expiry_dialog)` to defer it to the Tk event loop.

**User:** Good. One more thing — originally I was going to have the trial be 7 days but we changed it to 14 days after user feedback. The constants file still says 7 somewhere.

**Claude:** I'll update it. `TRIAL_DAYS = 14` in `trial_manager.py`. The v1 value of 7 is now deprecated.

**User:** Great. Let's also make sure TrialManager connects to LicenseDB and the main app. If TrialManager breaks, the whole app won't start.

**Claude:** Understood. TrialManager has HIGH blast radius — it's the first thing called in `main_app.py` startup sequence.

---
*End of export*
