# Analysis question bank

What we can ask of 9,764 accounts / 12.86M words across three corpora.
Purely descriptive: every question below is about **what the texts say**, not
about what caused the experiences.

## What we're working with

| Corpus | Accounts | Words | Nature |
|---|---|---|---|
| nderf | 5,750 | 8.19M | Near-death experiences; ~50 standardized questions |
| adcrf | 1,766 | 1.85M | After-death communication; ~40 standardized questions |
| oberf | 2,248 | 2.82M | OBE / STE / prebirth / deathbed vision / dream / UFO etc. |

The decisive asset: this is **a survey, not a text dump**. Roughly 5,300–5,700
NDERF respondents answered each of the same ~50 questions, so frequencies,
cross-tabs and correlations are directly computable rather than inferred from
prose.

Field coverage as extracted:

- Gender: 5,563 NDERF accounts (55.8% F / 44.2% M)
- Religion before / religion now: 5,358 / 5,292
- Date experience occurred: 5,344
- Country / Age / Classification: only ~1,250 (22%) — see A5

---

## A. Corpus baseline (answer before anything else)

1. How many distinct people, not accounts? Do repeat contributors exist across sites?
2. Length distribution of narratives — mean, median, tail. What does a 15,000-word account look like vs a 200-word one?
3. What is the actual response rate per question, and which questions were added or dropped over time?
4. How many accounts are translations, and from which languages?
5. Can we raise Country/Age/Classification coverage from 22% to near-complete by re-running the API enrichment with partitioned queries? (Demographic analysis is crippled at 22%.)
6. How many accounts describe multiple separate experiences in one submission?
7. What is the distribution of submission year vs. experience year — how long do people wait before writing?
8. How many accounts are second-hand (someone describing another person's experience)?

## B. Element census — the core "what are people saying"

The headline deliverable: a frequency table of every reported element.

9. Base rate of each canonical element: OBE/separation, tunnel, light, life review, border/point of no return, deceased beings, unearthly realm, ineffability, altered time, sudden total understanding, telepathy, music/sounds, being of light.
10. Which elements are near-universal, which are rare, and where does the frequency curve fall off?
11. How many elements does a typical account report? Distribution of element count.
12. Which elements co-occur far more than chance? Which almost never co-occur?
13. Are there natural clusters of accounts — recurring "types" of experience — or is it a continuum?
14. What elements appear frequently in free text but are **absent from the questionnaire** (i.e. things the researchers never thought to ask)?
15. What's in the long tail — elements reported by fewer than 20 people?
16. How often does an account explicitly report the *absence* of a canonical element ("there was no tunnel")?
17. Sensory breakdown: vision, hearing, touch, smell, taste, and senses described as non-physical or new.
18. Reported colours, and whether colour vocabulary exceeds ordinary range.

## C. Sequence and structure

19. In what order do elements occur? Is there a dominant sequence, or many?
20. Can accounts be modelled as state transitions (body → separation → transit → realm → encounter → border → return)? What are the transition probabilities?
21. Which elements act as "gateways" — rarely appear unless a prior element did?
22. Where do accounts terminate, and does termination point correlate with anything?
23. How long do people say it lasted, and how does subjective duration compare to reported clock time?
24. Do longer narratives report more elements, or just more detail on the same elements?

## D. Beings and entities

25. Who is met, and at what rates: deceased relatives, deceased friends, strangers, unidentified presences, religious figures, guides, angels, beings of light, non-human/animal, children.
26. How often is a met being someone the experiencer did not know was dead?
27. How often is a *living* person encountered?
28. Are pets and animals reported? At what rate?
29. How are beings identified — by sight, by knowing, by voice?
30. What proportion of religious-figure encounters name a specific figure vs. describe an unnamed presence?
31. Does the identity of religious figures track the experiencer's stated prior religion, or not?
32. How often are beings described as hostile, indifferent, or frightening rather than benevolent?
33. Are there recurring described features — appearance, clothing, age, luminosity?
34. How often does communication occur without speech, and how is that described?

## E. Environments

35. What settings are described: void, darkness, garden, city, library, fields, water, buildings, stairs, gates?
36. Frequency of "realer than real" or hyper-real descriptions.
37. How often is the environment described as familiar or as "home"?
38. Reported architecture and structures — any recurring specifics?
39. Landscape vs. featureless space — proportions.
40. How often is the environment described as changing in response to thought?

## F. Affect and valence

41. Emotion frequency during the experience: peace, love, joy, fear, terror, confusion, anger, sadness, awe, loneliness.
42. What proportion of accounts are predominantly distressing? This is a frequency question — report the rate whatever it is, without smoothing.
43. What distinguishes distressing accounts structurally — different elements, or the same elements framed differently?
44. Do distressing accounts resolve, and how often?
45. Emotion during vs. emotion after — do they match?
46. How often is the *return* described as unwanted, grievous, or resented?
47. Emotional vocabulary richness — do people reach for superlatives, and which?
48. How often is the experience described as the best/worst thing that ever happened?

## G. Knowledge, messages, teaching

49. What content is reported as learned or understood?
50. Frequency of specific claim types: purpose of life, nature of time, unity/oneness, reincarnation, judgment, universal love, the primacy of love, forgiveness, everything being alive/conscious.
51. How often is knowledge described as received-then-forgotten?
52. Life review: how often, from whose perspective, with what emotional content, and is it evaluative or neutral?
53. How often is the experiencer shown their own future, or world/global future events?
54. Are there recurring specific "messages" phrased similarly across unrelated accounts?
55. How often does the content contradict the experiencer's stated prior beliefs?
56. Frequency of claims about physics, cosmology, or scientific concepts.
57. How often are questions asked *of* the experiencer, and what are they?

## H. The border and the return

58. How is the boundary described, and how often is it a physical structure vs. a knowing?
59. Return: chosen, forced, sent back, or negotiated — at what rates?
60. What reasons are given for return? (children, unfinished task, someone's prayers, being told it isn't time)
61. How often is a specific reason given at all vs. no explanation?
62. How often is a promise, mission, or instruction reported as a condition of return?
63. How is re-entry to the body described?
64. Do return-type and emotional aftermath correlate?

## I. Aftereffects

65. Reported changes in values and beliefs — rate and direction.
66. Religion before vs. religion after: full transition matrix. Who changes, who doesn't, and toward what?
67. How often does someone move toward "spiritual but not religious" vs. toward organized religion vs. away from belief?
68. Reported loss of fear of death — rate.
69. Claimed psychic/paranormal abilities afterward — rate and type.
70. Reported electrical/electronic effects.
71. Life disruption: divorce, career change, estrangement, isolation.
72. Reported difficulty reintegrating, depression, or longing to return.
73. Disclosure: who did they tell, how soon, and what was the response?
74. How often was the account met with disbelief or ridicule, and from whom (family, clergy, medical staff)?
75. Reported changes in empathy, purpose, materialism, risk tolerance.
76. Do aftereffects intensity correlate with experience "depth" (element count)?
77. Time-since-experience vs. reported certainty — does conviction strengthen or fade?

## J. Demographics and correlations

78. Gender: does element frequency differ? (n≈5,563 — well powered)
79. Age at experience: do children's accounts differ in content, length, or vocabulary?
80. Do accounts from childhood recalled decades later differ from recent ones?
81. Country/region differences in reported content.
82. Prior religion vs. content — does it predict the identity of beings, presence of judgment, or realm description?
83. Does prior familiarity with the NDE literature correlate with more canonical accounts? (There's a direct question about prior knowledge — this is a testable expectancy effect.)
84. Occupation/education signals where inferable.
85. Does gender of experiencer correlate with gender of encountered beings?
86. Any interaction effects — e.g. does the country effect differ by age cohort?

## K. Culture, language, geography

87. Non-Western vs. Western accounts — what differs, what doesn't?
88. Do translated accounts show different element rates than English-origin ones? (Confound: translation flattens idiom.)
89. Religious-figure identity by country and by stated religion.
90. Does the tunnel/light/life-review triad hold cross-culturally at the same rates?
91. Are there elements that appear *only* in specific regions or language groups?
92. How does the corpus's geographic distribution compare to internet-population distribution (i.e. is this a US-heavy artifact)?

## L. Medical and circumstantial context

93. Precipitating events: cardiac arrest, accident, surgery, childbirth, drowning, illness, suicide attempt, allergic reaction, anesthesia, none.
94. Element frequency by precipitating cause — does cause predict content?
95. How often is clinical death claimed vs. a life-threatening event without it?
96. Anesthesia/medication involvement — self-reported rate.
97. Are drug- or substance-associated accounts distinguishable in content?
98. Do accounts with no life-threatening event at all (a real subset) differ from those with one?
99. Reported duration of unconsciousness vs. richness of account.
100. Suicide-attempt accounts: how do they differ in content and aftermath? (Handle carefully as a topic; the frequency question is legitimate.)

## M. Temporal trends (1998–2026)

101. Does reported content change across submission decades?
102. **Critical confound:** the NDERF questionnaire changed (~23 questions in form 1.0, ~50–57 in 1.1). Any trend must be tested against questionnaire version before it means anything.
103. Do narratives get longer, shorter, more canonical over time?
104. Does vocabulary shift — do later accounts use terminology popularized by earlier ones?
105. Are there spikes following major media events or books?
106. Does the age distribution of contributors shift over time?
107. Experience-year distribution vs. submission-year — what's the lag, and is it changing?

## N. Cross-corpus comparison (a real strength)

108. NDE vs. OBE vs. STE vs. ADC vs. prebirth vs. deathbed vision: which elements are shared, which are unique to one type?
109. Is there a common core across all experience types, or are they distinct phenomenologies?
110. Do ADC accounts (contact with deceased) describe the deceased the same way NDE accounts describe encountered beings?
111. Are shared-death experiences (multiple witnesses) different from solo accounts?
112. Do OBE accounts without a life threat contain the "transcendent" elements at all, or only the separation elements?
113. Dream vs. waking-vision vs. NDE — do these separate cleanly on content, or blur?
114. Does the same person ever appear across corpora with different experience types?
115. Which corpus has the highest rate of distressing accounts?

## O. Language and style

116. Ineffability markers — "cannot describe", "no words", "beyond language". Rate and placement.
117. Hedging vs. certainty language, and whether it changes across the narrative.
118. Tense shifts — do people move to present tense at the experience's peak?
119. Pronoun usage — "I" vs "my body" vs third-person self-reference during separation.
120. Metaphor inventory: what are the recurring comparisons?
121. Do accounts converge on shared phrasing? Near-duplicate sentence detection across unrelated accounts.
122. Readability / vocabulary sophistication vs. reported content.
123. Sentence-length and punctuation patterns at emotional peaks.
124. Are there phrases that only ever appear in one experience type?

## P. Corroboration claims (descriptive only)

The question is *what is claimed and how specifically*, not whether it happened.

125. How often is a veridical claim made (perceiving something checkable)?
126. What kinds — conversations overheard, objects seen, events elsewhere, meeting someone not known to be dead?
127. How specific are the claims — vague vs. detailed?
128. How often is independent corroboration asserted, and by whom?
129. How often does the experiencer volunteer a mundane alternative explanation themselves?
130. Rate of explicitly reported *failed* or mistaken perceptions.

## Q. Outliers and counter-patterns

131. Which accounts are most dissimilar from everything else in the corpus?
132. Are there accounts that report *none* of the canonical elements? How many, and what do they report instead?
133. Internal contradictions — accounts whose questionnaire answers conflict with their narrative.
134. Which accounts most influenced the corpus's "canonical" picture by being unusually long or widely cited?
135. Are there near-duplicate submissions (same story submitted twice, or plagiarized)?
136. What does the corpus look like if the top 1% longest accounts are removed — do headline stats change?

## R. Data-quality confounds (must be stated alongside any finding)

These aren't objections to the content. They're the difference between a real
pattern and an artifact of how the data was collected.

137. **Self-selection.** Contributors chose to submit to an NDE research site. Nothing here estimates population rates — only the composition of this corpus.
138. **Questionnaire framing.** Asking "did you pass through a tunnel?" invites a yes/no on a specific element. Free-text-only mentions and prompted answers must be counted separately, or prompting inflates every rate.
139. **Questionnaire drift.** Form 1.0 vs 1.1 changed both question count and wording. Segment before trending.
140. **The site's own AI tags.** NDERF ships AI-generated element tags. Using them as ground truth and then "discovering" those elements is circular. Derive independently; use theirs only as a comparison.
141. **Editorial curation.** "Exceptional" is an editor's judgement, not a property of the account.
142. **Translation.** The corpus is served translated; idiom, metaphor and hedging don't survive translation intact. Flag translated accounts in every language analysis.
143. **Recall interval.** Many accounts are written decades later. Test every content finding against time-since-experience.
144. **Answer-format parsing.** Coded prefix + free text. Under-parsing systematically undercounts "Yes". Validate the parser against a hand-labelled sample before trusting any percentage.
145. **Multiple comparisons.** With ~50 questions and many subgroups, some "significant" correlations will be noise. Pre-register the primary questions; treat the rest as exploratory.
146. **Denominator discipline.** Every percentage needs its base stated — of all accounts, or of those who answered that question? These differ a lot.

---

## Suggested sequencing

**Tier 1 — cheap, high value, no modelling.** A1–A8, B9–B12, F41–F42, I65–I69,
J78–J79, N108. Straight counts from parsed fields. Gives the headline census.

**Tier 2 — cross-tabs and correlations.** J, K, L, I66 transition matrix,
M101–M103 with the version confound controlled.

**Tier 3 — NLP required.** C sequences, D–E free-text element extraction,
O linguistics, P claim detection, Q outlier detection, B14 (unasked elements) —
this one is the most likely to produce something genuinely new, since it looks
for what the questionnaire never prompted.

**Prerequisite for all of it:** the answer normalizer (R144) and a decision on
prompted-vs-spontaneous counting (R138). Those two determine whether every
number downstream is right.
