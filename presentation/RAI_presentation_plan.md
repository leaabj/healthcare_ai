# Responsible AI presentation: structure, script and screenshots

This is the written version of `RAI_dashboard_slides.pptx`. Each slide below lists what is on screen, how to read its dashboard screenshot, and the words to say (the same text is in the speaker notes of the deck). Numbers come from the notebook's Section 9 and from the dashboard, which runs on 1,999 patients the score was never trained on.

**Timing.** 19 slides, about 14 minutes 49 seconds at a calm speaking pace. For a 10-minute slot, skip the slides marked *optional*: that leaves about 11 minutes 27 seconds.

**How the slides work.** Every dashboard slide shows its screenshot as large as possible. Orange numbered circles on the screenshot match a numbered key next to it. In the script, numbers in square brackets such as [2] are pointing cues: point at circle 2 while saying that sentence, but do not read the number aloud. Finding slides end with a box called *What we tell the hospital*.

## Slide by slide

### 1. Who should the nurse call after discharge?  ·  about 27 s

**On screen:** Title. Subtitle: a readmission risk score for patients with diabetes, checked with Microsoft's Responsible AI dashboard.

**Say:** Imagine you are a nurse and 1,000 patients with diabetes go home this month. You have time to phone about 200 of them. Who do you call? We built a score to answer that, and then used Microsoft's Responsible AI dashboard to check where it goes wrong and what a hospital should do with it. No background needed: we will explain every chart.

### 2. Too many patients with diabetes come back too soon  ·  about 37 s

**On screen:** Three numbers: **1 in 10** back within 30 days; **~200** calls per 1,000 discharges (20 minutes each); **73,000** hospital stays from 130 US hospitals. Why a call helps. The question in a banner: using only the discharge chart, who should be called first?

**Say:** About one in ten patients with diabetes is back in hospital within a month. That is bad for them and expensive for the hospital. A short phone call after discharge can catch some of it early: a medicine mix-up, blood sugar out of control, a follow-up appointment that was never booked. But there is time for about 200 calls per 1,000 patients, about 20 minutes each. So the question is: from what is already in the chart on the day they leave, who should be called first?

### 3. A risk score built from the discharge chart  ·  about 48 s

**On screen:** Three steps: read 17 chart items → give a risk from 0% to 100% → everyone above **11.6%** goes on the call list (about the riskiest 1 in 5). The list is a suggestion; a nurse decides. Glossary box: readmission, previous stays, diagnoses, HbA1c ("diabetes report card"), insulin change, each with its dashboard name in grey.

**Say:** Our tool is a simple statistical score. It reads 17 things already written in the chart at discharge, like age, previous hospital stays, number of diagnoses and the HbA1c blood test, and turns them into a risk between 0 and 100 percent. Everyone above 11.6 percent goes on the call list: roughly the riskiest one in five, which matches the 200 calls. The list is only a suggestion; a nurse still decides. Two words to remember. HbA1c is the diabetes report card: a blood test for average sugar over the last few months. And previous stays means hospital stays in the year before. The grey names are what the dashboard calls them.

### 4. How good is the call list? Four boxes tell the story  ·  about 55 s

**On screen:** The dashboard's confusion matrix for 1,999 patients the score never saw, with four numbered markers and a plain-language key.

**Screenshot:** `screenshots/01_confusion_matrix.png`

**How to read it:**
- Rows (True Class): did the patient come back? 1 = yes, 0 = no. Columns (Predicted Class): did we put them on the call list?
- 1 = 84 called and came back (the calls that matter). 2 = 311 called but fine. 3 = 138 came back but never called (the misses). 4 = 1,466 correctly left alone.
- Takeaway: about 1 in 5 calls reaches someone who comes back (twice as good as calling at random), but 6 in 10 of those who come back are never called.

**Say:** First dashboard screen: the confusion matrix. It is just four boxes. Rows: did the patient really come back? Columns: did we put them on the list? [1] Top right: 84 patients were called and did come back. Those are the calls that matter. [2] Below it: 311 were called but were fine, a call for nothing. [3] Top left: 138 came back and were never called. Those are the misses. [4] And 1,466 were correctly left alone. So one call in five reaches someone who comes back, twice as good as picking at random. But six in ten of the people who come back are never called, and on brand-new patients it looked the same. Honest summary: the list tells you who to call first, not who is safe.

### 5. The dashboard: one web page, six panels  *(optional)*  ·  about 37 s

**On screen:** Six thumbnails, one per panel, each with the question it answers. Note at the bottom: the dashboard assumes a 50% cut-off, so we set every panel to our 11.6% line.

**Screenshot:** `screenshots/thumbnails/`

**How to read it:**
- Error analysis: where are the mistakes? Model overview: how well does it work per group? Data analysis: what does the data look like? Feature importance: what does the score look at? Counterfactuals: what would flip a decision? Causal analysis: cause or coincidence?

**Say:** The dashboard itself is one web page with six panels. It does not build the score; it interrogates it. Where does the score make mistakes? Does it work equally well for different groups of patients? What does it look at? What would flip a decision? And is something a cause or just a coincidence? One setting mattered: the dashboard assumes a 50 percent cut-off. Almost nobody reaches that here, so it would show an empty call list. We set every panel to our real 11.6 percent line.

### 6. What does the score look at? Mostly one thing  *(optional)*  ·  about 41 s

**On screen:** The dashboard's aggregate feature importance chart, large, with three markers and the key on the right.

**Screenshot:** `screenshots/02_feature_importance.png`

**How to read it:**
- Each bar is one chart item; a taller bar means the score's answer moves more when that item changes.
- 1 = previous hospital stays (number_inpatient; the dashboard cuts its label short), twice as tall as anything else. 2 = diagnoses, insulin change, age, HbA1c. 3 = gender and race: small, not zero.
- The other small bars hardly matter; nobody needs to read every name.

**Say:** What does the score look at? Each bar is one item from the chart; the taller the bar, the more the score reacts to it. [1] One bar towers over everything: previous hospital stays. It counts twice as much as the next item. [2] Then come diagnoses, insulin changes and age. [3] Gender and race have small bars, which is good, but small is not zero, so we also checked groups separately. The other small bars hardly matter, so we will not read every name. Remember the first bar: most of what follows comes from it.

### 7. Where does the score go wrong? The error tree  ·  about 56 s

**On screen:** The error analysis tree (cropped to the tree so its labels are readable) with the worst group selected, four markers, key on the right.

**Screenshot:** `screenshots/03_error_tree.png`

**How to read it:**
- 1 = top circle: all 1,999 patients; "449/1999" = 449 wrong decisions (a call for nothing or a miss).
- 2 = each branch is a yes/no question the tool picked itself ("number_inpatient > 0.00" = any previous stay).
- 3 = redder circle: wrong more often in that group; fuller circle: more of all mistakes sit there.
- 4 = worst group, 2 to 6 previous stays: 178 of 267 wrong (67% against 22% overall), 40% of all mistakes.
- In the dashboard, clicking a circle also shows its numbers on the right: 267 patients, 89 right, 178 wrong.

**Say:** The error tree hunts for groups of patients where our decisions are often wrong. [1] Start at the top: that circle is everyone. 449 over 1,999 means 449 wrong decisions, either a call for nothing or a miss: 22 percent. [2] From there the tool splits patients with yes-or-no questions it picked by itself, and it asks about previous stays three times in a row. [3] Read the circles by colour and fill: the redder the circle, the more often we are wrong in that group; the fuller it is, the more of all our mistakes sit there. [4] Follow it down to the darkest circle: patients with 2 to 6 previous stays. 178 wrong out of 267: 67 percent, three times the average, and 40 percent of all our mistakes.

### 8. Finding 1: regular patients get called on autopilot  ·  about 59 s

**On screen:** The model overview table (first four patient groups) at full width; the 2-to-6-previous-stays row outlined in orange, all patients in teal; column markers above the table. Three boxes: reading the columns, what it shows, what we tell the hospital.

**Screenshot:** `screenshots/04_patient_groups_table.png`

**How to read it:**
- 1 = Selection rate: share of the group we put on the call list. 2 = False positive rate: of those who did NOT come back, share we called anyway. 3 = False negative rate: of those who DID come back, share we missed. Darker blue = higher value in that column.
- Shows: 2 to 6 previous stays → 86% called (everyone 20%); 3 in 4 of those calls are for nothing (170 of 230); they do come back more (25% vs 11%).
- Tell the hospital: for patients with 2+ previous stays a nurse decides after reading why they were admitted; add the reason for admission to the next version.

**Say:** Why are we wrong there? The model overview table compares groups of patients, one per row, and three columns matter. [1] Selection rate: how many of the group we call. [2] False positive rate: of those who were fine, how many we called anyway. [3] False negative rate: of those who came back, how many we missed. Now look at the orange row. Patients with 2 to 6 previous stays get a call 86 percent of the time, against 20 percent overall, and three out of four of those calls are for nothing. The score cannot tell which regulars will come back; it just thinks: been here before, will be back. So for regulars, a nurse should decide after reading why they were admitted, and the next version of the score should know the reason for admission.

### 9. Finding 2: the same table, split by age  *(optional)*  ·  about 45 s

**On screen:** The model overview table by age group; over-80 rows outlined in orange, the 50s in teal; three markers, key on the right.

**Screenshot:** `screenshots/05_age_groups_table.png`

**How to read it:**
- Rows are sorted by size, not by age.
- 1 = called: 33% of 80–89s and 46% of over-90s, against 12% in the 50s. 2 = of the 80–89s who were fine, 32% were called anyway (50s: 10%). 3 = misses do not climb with age: about half to two-thirds of those who come back are missed at every age.

**Say:** Same table, now split by age. Careful: the rows are sorted by size, not by age. [1] People aged 80 to 89 are called 33 percent of the time and over-90s 46 percent, while people in their fifties are called 12 percent of the time. [2] Among the 80 to 89 year-olds who were fine, one in three got a call anyway; in the fifties, one in ten. [3] The misses do not climb with age the way the calls do: at every age we miss between about half and two-thirds of those who come back. So age mainly decides who gets the extra calls.

### 10. Finding 2: twice the calls for over-80s, same return rate  ·  about 55 s

**On screen:** Native bar chart by age group: share put on the call list (orange) against share who actually came back (teal). Boxes: what it shows, why, what we tell the hospital.

**How to read it:**
- Over 80: 35% called, 10% came back. Age 50–79: 16% called, 10% came back. Only 1 in 8 calls to an over-80 reaches someone who returns (1 in 5 for 50–79).
- Why: the score adds a little risk for very old age and for each extra diagnosis, and over-80s have more diagnoses on file.
- Tell the hospital: one rule for everyone, but a clinician checks the over-80 names before calls go out; no separate age cut-off without an ethics review.

**Say:** Here is the same thing as a picture. Orange: how many we call. Teal: how many actually came back. From 50 to 79 the bars are close: 16 percent called, 10 percent back. Over 80, the orange bar doubles to 35 percent, but the teal bar stays at 10. So only one call in eight to an over-80 reaches someone who returns. Why? The score adds a little risk for very old age and for every extra diagnosis, and old patients have more diagnoses written down. What we would tell the hospital: keep one rule for everyone, because a special age rule needs an ethics review, but have a clinician look at the over-80 names first. For a frail 88-year-old, an unnecessary call is a burden, not a favour.

### 11. What would have to change? The what-if tool  ·  about 54 s

**On screen:** The counterfactual (what-if) scatter, large: risk left to right, previous stays up and down, our call line marked; the patient selector with patient 248 and the what-if button on the right.

**Screenshot:** `screenshots/06_what_if_map.png, 06b_what_if_selection.png`

**How to read it:**
- 1 = left to right is risk; the scale is stretched so 0.5 is exactly our 11.6% line (right of it = on the list).
- 2 = up = more previous stays; one dot per patient. The staircase: nobody with 3+ previous stays is left of the line, almost nobody with 0 is right of it.
- 3 = patient 248 sits right on the line. 4 = the button asks for the smallest chart change that flips the decision. Only the HbA1c result, insulin change, any diabetes-medicine change and on/off diabetes medicine were allowed to change.

**Say:** Next, the what-if tool. Each dot is a patient. [1] Left to right is risk, and we stretched the scale so that 0.5 is exactly our call line: right of it, you are on the list. [2] Up and down is the number of previous stays. See the staircase? Nobody with three or more previous stays is left of the line, and almost nobody with zero is right of it. [3] Now pick one patient, number 248, who sits right on the line, [4] and press this button. It asks: what is the smallest change to his chart that flips the decision? We only let it change what the ward writes down during the stay, the HbA1c result and the diabetes medicines. Age and history stayed fixed.

### 12. Finding 3: one line of paperwork can decide who gets a call  ·  about 56 s

**On screen:** Two patient cards side by side: patient 248 as recorded (HbA1c not measured, risk 11.8%, ON the list) and the same patient with one change (HbA1c above 8, risk 9.6%, OFF the list). He was back within 30 days. Big number: **36%** of patients (716 of 1,999) cross the line through these entries alone.

**How to read it:**
- Tell the hospital: the list partly reflects how things were written down. Never change a test or medicine to move a score; record these items the same way on every ward; re-check the list if habits change.

**Say:** Here is the answer for patient 248. A man in his seventies, never admitted before, insulin lowered during the stay, no HbA1c test. Risk 11.8 percent: just on the list. Same man, one change: the HbA1c test was done and came back above 8. Risk 9.6 percent: off the list. What really happened? He was back in hospital within 30 days. And he is not alone: for 36 percent of patients, changing only these paperwork items moves them across the line. So the list partly measures how things were written down. The message: never change a test or a medicine to move a score, and record these things the same way on every ward. You may wonder why a high sugar result would lower the risk. That is our next question.

### 13. Cause or coincidence? Reading the causal chart  *(optional)*  ·  about 42 s

**On screen:** The causal analysis chart (effect of each HbA1c result against no test), large, three markers, reading key on the right.

**Screenshot:** `screenshots/07_causal_effects.png`

**How to read it:**
- 1 = each column compares patients with one HbA1c result to similar patients never tested (">8vNone" = above 8 versus not measured).
- 2 = the dot is the best estimate: −0.03 = 3 fewer readmissions per 100 patients. 3 = whiskers are the uncertainty; crossing 0 means we cannot tell it from no effect.
- "Similar" = same age, previous stays, diagnoses and so on. The dashboard's table of the same numbers is shown in plain words on the next slide.

**Say:** The causal panel asks a different question: does doing something change the outcome? We asked about the HbA1c test. [1] Each column compares patients with one test result to similar patients who were never tested; similar means the same age, previous stays, diagnoses and so on. [2] The dot is the best estimate: minus 0.03 means three fewer readmissions per 100 patients. [3] The whiskers show how unsure we are. If they cross the zero line, like the first two columns, we cannot tell the effect apart from nothing. Only one column sits clearly below zero: results above 8.

### 14. Finding 4: a high HbA1c result goes with fewer returns  ·  about 65 s

**On screen:** A plain-words version of the dashboard's causal table: above 8 = 3 fewer per 100 (range 1 to 5 fewer), unlikely to be luck (p = 0.004); normal = 1 fewer (4 fewer to 2 more), can't tell (p = 0.54); 7 to 8 = about 0 (4 fewer to 3 more), can't tell (p = 0.95). A one-line p-value explanation. Two explanations (cause or coincidence) that the data cannot separate; 83% of stays had no HbA1c test at all.

**Screenshot:** `screenshots/07b_causal_table.png (dashboard original, backup only)`

**How to read it:**
- Tell the hospital: keep measuring HbA1c and acting on high results (cheap, good practice), but do not promise fewer readmissions until a proper study tests it.

**Say:** The dashboard also lists these numbers in a table; here they are in plain words. Patients whose HbA1c was measured and above 8 came back about three times less per hundred than similar untested patients, and a p-value of 0.004 says that is unlikely to be luck. For normal results and 7 to 8 we cannot tell. Why would worse sugar mean fewer returns? Two stories. Cause: a high result makes doctors fix the diabetes treatment before the patient leaves. Coincidence: wards that bother to test also plan discharges more carefully. This data cannot tell them apart. A striking detail: 83 percent of stays had no HbA1c test at all, and this is also why a recorded high result lowered patient 248's score. For the hospital: keep testing and acting on high results, because it is cheap and good practice, but do not promise fewer readmissions until a proper study checks it.

### 15. Warning: the tool's recommended treatment is backwards  ·  about 51 s

**On screen:** The treatment policy rule and the policy gains chart side by side, three markers, arrows under the chart (left = fewer readmissions, good; right = more, bad), and a lesson banner.

**Screenshot:** `screenshots/08_treatment_policy_rule.png, 09_treatment_policy_gains.png`

**How to read it:**
- 1 = the rule: patients with a previous stay should "get" an HbA1c above 7. A test result is not a treatment.
- 2 = bars: change in readmissions if everyone had that result; the long bar left (−0.031) is the best news.
- 3 = the tool assumes bigger is better, so its "recommended policy gain" (+0.007) is the plan that raises readmissions. Checked in the econml code: the policy picks the option with the highest outcome, and our outcome is readmission.

**Say:** One more causal screen, and it is a warning. The dashboard offers a recommended treatment. [1] Its rule says patients with a previous stay should get an HbA1c above 7. But a test result is not a treatment; you cannot prescribe a lab value. [2] The bars show how readmissions would change if everyone had that result. Readmission is bad, so the long bar to the left is actually the best news. [3] But the tool assumes bigger is better, so the plan it recommends, and calls a gain, would raise readmissions. We checked the library's code to confirm this. The lesson: the tool does not know that readmission is bad, so always check which direction counts as good.

### 16. Finding 5: the score only finds patients it already knows  ·  about 51 s

**On screen:** The patient groups table again; the no-previous-admission row in orange, 1+ previous admissions in teal; three markers on the cells.

**Screenshot:** `screenshots/04_patient_groups_table.png`

**How to read it:**
- 1 = first-timers who came back: 97% missed (107 of 110). 2 = only 2% of first-timers are on the list. 3 = patients with a previous stay who came back: 28% missed.
- Half of everyone who came back (110 of 222) had never been in hospital before.
- Tell the hospital: use the list for known frequent patients; normal discharge care stays for everyone; not on the list never means safe.

**Say:** The last finding is the most important. Back to the groups table, and look at the orange row: patients never admitted before. [1] Of the first-timers who came back, we missed 97 percent, 107 out of 110, [2] because only 2 percent of first-timers make the list at all. [3] Compare the patients with previous stays: of those who came back, we missed 28 percent. And here is the problem: half of everyone who came back had never been in hospital before, so the score is almost blind to half of the problem. The message: use the list for the known frequent patients, keep normal discharge care for everyone, and never read "not on the list" as "safe".

### 17. Why was she missed? Meet patient 21  *(optional)*  ·  about 37 s

**On screen:** Patient strip (woman in her 60s, 9 diagnoses, 4 days, no previous stays, HbA1c not measured, risk 7.5%, not called, back within 30 days) above the dashboard's explanation chart for her.

**Screenshot:** `screenshots/10_patient21_explanation.png`

**How to read it:**
- Bars above 0 pushed her risk up, bars below 0 pushed it down.
- 1 = 9 diagnoses pushed her risk up the most. 2 = no previous stays pushed it down even more, so she stayed under the line.

**Say:** To make it concrete, meet patient 21: a woman in her sixties with nine diagnoses, four days in hospital, never admitted before. Her score was 7.5 percent, under the line, so no call, and she was back within 30 days. The dashboard can explain one patient at a time: bars above zero pushed her risk up, bars below zero pushed it down. [1] Her nine diagnoses pushed it up, [2] but "no previous stays" pushed it down even harder. Her chart simply did not look risky.

### 18. What we tell the hospital  ·  about 55 s

**On screen:** Three columns. **Do:** use the list to order calls within ~200 per 1,000; nurse review of 2+ previous stays and over-80s; normal discharge care for everyone; monthly check that ~200 per 1,000 are listed and at least 15% of those called come back (1 in 5 today). **Don't:** change tests or medicines to move a score; read "not on the list" as "safe"; age-specific cut-offs without ethics review; follow the dashboard's "recommended treatment" at face value. **Next:** add the reason for admission; test on this year's patients; run a trial of the calls.

**Say:** So what do we tell the hospital? Do: use the list to decide who to call first; have a nurse review the regulars and the over-80s; keep normal discharge care for everyone; and check every month that the list stays around 200 per 1,000 and that at least 15 percent of the people called do come back. Today it is one in five, so dropping below 15 percent is the early warning. Don't: change care to move a score, treat "not on the list" as safe, make age rules without an ethics review, or follow the dashboard's recommended treatment. Next: add the reason for admission, test the score on this year's patients, and run a proper trial, because nothing we did shows that the calls actually prevent readmissions.

### 19. Closing  ·  about 18 s

**On screen:** "The score is a good memory of who has been here before. It is not a crystal ball." Use it to put the calls in order; keep people in charge. Questions?

**Say:** If you remember one sentence: the score is a good memory of who has been here before, but it is not a crystal ball. Use it to put the calls in order, and keep people in charge of the decisions. Thank you. Questions?

## Dashboard words in plain language

| Dashboard term | What it means here |
|---|---|
| True Class / TrueY | What really happened: 1 = came back within 30 days, 0 = did not |
| Predicted Class / PredictedY | What the score did: 1 = on the call list, 0 = not |
| Selection rate | Share of a group put on the call list |
| False positive rate | Of the patients who did NOT come back, the share we called anyway |
| False negative rate | Of the patients who DID come back, the share we missed |
| Accuracy score | Share of right decisions. Misleading here: calling nobody would already be 89% accurate |
| Error rate (error tree) | Share of wrong decisions inside a group |
| Error coverage (error tree) | Share of all our wrong decisions that sit in that group |
| Cohort | A group of patients defined by a rule, for example "no previous admission" |
| Feature importance | How much the score's answer moves when one chart item changes |
| Counterfactual (what-if) | The smallest change to a patient's chart that would move them to the other side of the call line |
| Causal effect | Estimated change in the chance of readmission caused by a factor, comparing similar patients |
| Confidence interval / whiskers | The plausible range for an estimate; if it crosses 0 the effect may be nothing |

## Screenshots

All files are in `presentation/screenshots/`. They were taken from the dashboard built in the notebook (Section 9), with the patient groups defined as cohorts and the score's real 11.6% call line, in a narrow browser window so the dashboard's own text comes out large on the slides. The what-if map comes from the same patients re-run with the call line placed at the middle of the dashboard's scale, as in notebook Section 9.5.

| File | Dashboard panel | Slide |
|---|---|---|
| `01_confusion_matrix.png` | Model overview, confusion matrix | 4 |
| `02_feature_importance.png` | Feature importance, aggregate | 6 |
| `03_error_tree.png` | Error analysis, tree map, worst group selected | 7 |
| `04_patient_groups_table.png` | Model overview, dataset cohorts | 8, 16 |
| `05_age_groups_table.png` | Model overview, feature cohorts by age | 9 |
| `06_what_if_map.png`, `06b_what_if_selection.png` | Counterfactuals map and the patient selector with patient 248 | 11 |
| `07_causal_effects.png` | Causal analysis, aggregate effects chart | 13 |
| `07b_causal_table.png` | Causal analysis, the same effects as a table (backup) | 14 |
| `08_treatment_policy_rule.png` | Causal analysis, treatment policy rule | 15 |
| `09_treatment_policy_gains.png` | Causal analysis, treatment policy gains | 15 |
| `10_patient21_explanation.png` | Feature importance, one patient | 17 |
| `thumbnails/*.png` | One small picture per panel | 5 |

## Likely questions

- **Why 11.6%?** It is the line that puts about 200 patients per 1,000 on the list, the number of calls nurses can make. It was fixed before the final test.
- **Isn't 6 in 10 missed terrible?** It is the honest price of 200 calls: many patients who come back look low-risk in the chart (finding 5). The point is to order the calls, not to promise safety.
- **Why not balance the data or resample?** We kept the real proportions so the risks stay true percentages, and handled the imbalance by choosing the call line from nurse capacity.
- **Is the score unfair?** It leans little on race and gender directly. The unfairness we found is about who gets unnecessary calls (over-80s) and who is invisible (first-timers), not who is refused care.
- **Does calling actually prevent readmissions?** We cannot tell from this data: no calls were recorded. That needs a trial, which is our main next step.
- **Did the causal analysis compare like with like?** It adjusted for age, previous stays, diagnoses and the other chart items. It also held constant a few things recorded later in the stay, such as medicine changes; leaving those out gave almost the same answer (3.4 instead of 3.1 fewer per 100). Unmeasured differences between wards can still explain it.
- **Why did the what-if map use a stretched scale?** The dashboard's what-if tool always flips at 0.5. We stretched the scale, without changing the order of patients, so that 0.5 equals our 11.6% line.
