# Decisions

## 01 The visit

I would send the technician to S02 station first, as it was mentioned its pressure board was changed but it wasn't calibrated. Pressure is important for the network's climate summary, and a sensor can produce plausible-looking readings while still having a calibration offset.

During the 1-hour visit, I would first compare the station's pressure reading with a trusted reference instrument. Then I would check the board's installation, calibration settings and recent readings, and record any adjustment made. I would not change historical readings without knowing the timing of the error.

S05 would be my second choice. Its humidity readings reached 104% for 21 consecutive readings, and the maintenance notes also mention concerns about humidity staying around 100%. That deserves investigation, but the observed run is much shorter than the 24-hour threshold used by my checker. In my checker, I used a 24-hour threshold. S02 has a specific, unresolved calibration issue documented in the maintenance notes.

## 02 My least-certain decision

The duplicate-timestamp flag for S08 needs a closer look. The checker identified 144 rows with duplicate timestamps and grouped them into a single review flag for the station. This could be due to repeated uploads or a logger issue, but duplicate timestamps alone don't necessarily mean that all those observations are invalid.

I would first compare the weather values in the duplicated records to check whether they are identical or different. The most helpful additional information would be the logger or transmission log, which could clarify whether the records were retransmitted or recorded separately. Until that is confirmed, I would keep this as a review flag rather than automatically deleting the affected records.

## 03 Where the AI was wrong

One issue I found was in the pressure formula. An earlier version used `22.55e-5` instead of `2.255e-5`, which resulted in expected pressure values that were much lower than realistic atmospheric pressure. I caught this by reviewing the formula and comparing its output with typical pressure values, then corrected the coefficient.

I also found a problem with GPS parsing. The earlier logic did not handle `.nmea` files properly and checked the wrong field for the RMC fix status. Since the status is stored in the third comma-separated field (`fields[2]`), the parser could miss invalid fixes. I fixed the file filtering and status-field check, then reviewed the issue counts in the generated output to make sure the changes were reflected.

## 04 If this ran on 500 stations next year

I would improve the system by adding structured logs, automated tests, configurable thresholds, and a severity score to help the coordinator focus on the most important issues first. Repeated events could be grouped together to avoid unnecessary alerts, while cases with a high level of confidence or a potentially serious impact would be prioritised for review. I would also track how often flagged issues are confirmed or dismissed and use that feedback to fine-tune the thresholds over time.

At the same time, I would be careful not to treat every unusual reading as an error. For example, a brief humidity flatline does not necessarily mean that the entire period should be excluded. I would also avoid automatically deleting or modifying historical climate data without clear evidence and a proper review process. Any changes should be traceable and allow a person to make the final decision.