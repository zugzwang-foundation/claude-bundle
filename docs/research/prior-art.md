# Prior art: how chats are organised today, and what Bundle adds

Status: DRAFT — research note, 2026-10-16.

## The question

Three things, in order. (a) How do ChatGPT, Claude, Gemini and Grok let people organise their chats today: projects, folders, memory, search, pinning, and any automatic grouping? (b) Which browser extensions and tools already sort or folder chats, and how? (c) What research and datasets exist on organising chat histories: topic segmentation, conversation clustering, multi-session memory, intent clustering, and the older problem of filing items into a person's own evolving set of folders? Then: where Bundle genuinely differs (a small open decision model in the browser, probabilities with an explicit "none", synthetic-only training, a public sealed exam), where it does not, and where the relay's picture is wrong.

Every fact below comes from a page opened on 16 October 2026; numbers in square brackets point to the Sources list. Where a page could not be opened or did not say, the text says "unknown".

## Findings

### A. The four products, from their own help pages

**ChatGPT (OpenAI).** Projects "keep related chats, files, and instructions together" [1]. A chat gets into a project by hand: drag it onto the project, or open the chat's menu and choose "Move to project"; chats started with a GPT cannot be moved; a moved chat inherits the project's instructions and files; "Remove from project" sends it back to the plain history [1]. Projects have default or project-only memory, switchable after creation since 14 August 2026; shared projects are always project-only [1][3]. File and collaborator limits: Free 5 files and 5 collaborators, Plus and Go 25 and 10, Pro 40 and 100 [1]. Sidebar search covers chats, projects, images and documents on every plan, matches words in a chat's title or messages, includes archived chats, and has filters by content type [2]. The release notes (latest entry 15 October 2026) show a steady run of organisation work: pinned chats on 18 December 2025; pinning chats and projects from the sidebar, with one Pinned section for both, and a Recents view grouped by project (a view, not a sorter), on 18 June 2026; search across chats, projects and files redone on 14 July 2026; desktop "Unified Recents" with sort, filter and pin on 16 July 2026; search matching folders and conversation titles on 7 August 2026; the sidebar showing up to eight recent conversations on 21 August 2026; and on 29 September 2026 "Space", which gathers Pages, files and related work and replaces Library for Pro, Business and Enterprise [3]. Memory now keeps itself up to date (4 June 2026), shows "memory sources" under personalised answers (5 May 2026) and has an editable memory summary (12 June 2026) [3]. The one content-based routing hint found anywhere: since 7 January 2026, a health question in a regular chat may get a suggestion to continue in the Health space [3]. Nothing in the help centre or the release notes files a chat into a project automatically. A user asked for exactly that on the OpenAI community forum; on 6 September 2026 OpenAI Support replied that projects already group chats by hand, that automatic sorting goes further, and that there was "No timeline to share yet" [4]. Projects launched on 13 December 2024, described by TechCrunch as a way to create custom folders for conversations, for Plus, Pro and Team first [5].

**Claude (Anthropic).** Projects are "self-contained workspaces with their own chat histories and knowledge bases"; every plan has them, free accounts up to five [6][7]. A chat is moved by hand from the dropdown next to its name ("Add to project"), and can be moved between projects or removed; projects can be starred for the sidebar [6]. Each project has its own memory; inside a project Claude uses that memory plus the person's account memory, but never another project's [8]. Memory is saved as individual topics as the person chats, is on by default for Free, Pro and Max, can be turned off per chat, and incognito chats stay out of history and memory [8]. Searching past chats is a paid-plan feature used by asking Claude in plain words; the search shows up as a tool call [8]. The help page on memory describes memory as saved topics and says nothing about organising or grouping chats [8]. The release notes (latest entry 7 October 2026) record search over past chats (11 August 2025), memory and incognito chats (11 September 2025), memory as "individual, categorized entries" (10 July 2026) and memory shared across chat and Cowork (25 August 2026), but no entry at all for pinning, grouping or sidebar organisation [9]. A new beta treats a project as one conversation with parallel threads and a Library of files [7].

**Gemini (Google).** The help page on managing chats lists exactly: a side panel of pinned and recent chats, keyword search, Pin and Unpin, Rename, Delete, and "Branch in a new chat"; with Keep Activity and Memory on, a person can ask Gemini about past chats "by topic or timeframe" [10]. No folders, projects or grouping appear on that page [10]. Gems are custom assistants with instructions and optional files; the page gives no sign that chats are assigned to a Gem automatically, and says that from November 2026 Gems on personal accounts go away and become "skills" [11]. Memory of past chats ("Personal Intelligence") needs an adult personal account with Keep Activity on, can be switched off in settings, and is not available inside Gems or Live [12]. Nothing on these pages groups chats.

**Grok (xAI).** The public Projects page shows only its tagline, "Create custom workspaces, upload files for smarter chats, and collaborate securely", and asks for sign-in [13]. Grok's release notes of 15 August 2026 confirm the shape: project conversations, project icons in the sidebar "with pagination for long lists", sharing a project shares its conversations, a memory summary whose text can be selected to correct or remove what Grok remembers, and chat history syncing across tabs [14]. The Grok Business guide describes Personal and Team workspaces and conversation sharing, and says nothing about folders, pinning, cross-chat search or automatic grouping [15]. Memory arrived in beta on 16 April 2025, outside the EU and UK, with a Data Controls switch and per-memory deletion [16]; a report of the next day describes workspaces as grouping related chats, files and instructions under one topic, by hand [17]. Whether consumer Grok today offers pinning or search across chats: unknown (the pages that would say so need sign-in).

**Across all four.** The same four tools everywhere: a manual container (project, workspace, Gem), a memory layer that personalises replies, keyword or natural-language search, and pinning. No product opened today assigns a chat to a container by itself, suggests one with a confidence, or publishes any accuracy for doing so. The spec's premise holds on the evidence, with one caveat: ChatGPT's Health nudge [3] and its 29 September "Space" [3] show OpenAI moving towards content-aware destinations, and its support team has the request on file [4].

### B. Extensions and tools that sort chats

Nearly every extension adds folders; very few sort for you, and none publishes a measurement.

- **Superpower for ChatGPT**: 100,000 users, 4.6 stars from 3.7K ratings, updated 16 October 2026; folders and subfolders, drag and drop, search; its only automation is "Automatically create folders for conversations started with Custom GPTs" [18]. The GitHub repository has 1.7k stars under a custom licence that forbids redistribution, commercial use and derivatives [19].
- **AI Toolbox** (formerly ChatGPT Toolbox, by Infi Developments): 40,000+ users, 4.7 stars; unlimited nested folders for ChatGPT, Gemini, Claude and Grok; folder structure syncs through an AI Toolbox account, so it lives in their cloud; premium $9.99 a month or $99 lifetime [20]. Its Smart Tags feature (page updated 24 June 2026) runs "locally in your browser", tags chats into five fixed topics (Coding, Writing, Research, Math & Science, Business), lets people add rules pairing a tag with keywords, tags the 50 most recent chats for free, and makes no accuracy claim; the page does not say how the built-in tagging decides [22].
- **Chat Organizer** (chat-organizer.com): auto-sorts into ChatGPT Projects using "a multilingual keyword wordlist and AI for the ambiguous ones"; reads titles only, sends ambiguous titles to "a shared AI service", scans up to 200 recent chats, shows a plan and applies it on approval; free, no API key [23]. The model and where it runs: unknown.
- **ChatFolders** (chatfolders.dev): ChatGPT, Claude and Gemini; the premium auto-categoriser sends chat titles to OpenAI, Anthropic or Google APIs with the person's own key and suggests folders; $4.99 a month, $29.99 a year or $49.99 lifetime; says it is open source [24]. Its Chrome listing has 113 users, 5.0 stars from 3 ratings, updated 5 May 2026, adds Grok, and describes only manual drag and drop with local storage [25].
- **ChatGPT Organizer – Smart Auto Folders & Search**: 148 users, 3.9 stars from 8 ratings, updated 21 August 2026; "Chats auto-organize into folders — no manual sorting required", for ChatGPT and Gemini, locally; method unstated [26].
- **AI Chat Navigator**: seven chat apps, local; automatic grouping into topic categories is listed as "Planned" [27].
- **Sortbase** (said to be formerly Easy Folders; NOT VERIFIED on the page opened): ChatGPT, Claude, Gemini, Grok; 20,000+ accounts; manual filing; $10 a month or $100 a year; stores filed chats on an encrypted cloud backend of a Texas company [28].
- Manual-only, small: AI Chat Organizer (25 users, updated 29 September 2025; ChatGPT, Claude, Perplexity, GitHub Copilot) [29]; ChatFolderz (45 users, 1.5 stars, updated 4 November 2024) [30]; ChatGPT Folders (21 users, updated 23 September 2025) [31]. LLMnesia indexes 14+ chat apps for local full-text search and does not cluster [32].
- Open source on GitHub: ChatGPT-Folderizr (GPL-3.0, 2 stars) folders by a "[Name]" tag typed into the chat title [33]; AIChatFolders (MIT, 0 stars) adds manual folders over ChatGPT, Gemini, Claude and DeepSeek and stores only folder metadata locally [34]. Mem0 also ships a browser extension that carries memories across ChatGPT, Perplexity and Claude [41].

Pattern: the auto-sorters that exist use keyword lists, fixed category sets, or a cloud LLM reading titles. None uses a model running in the page, none outputs a probability or a "none", none handles a person's own evolving bundles as the label set, and none publishes an accuracy, a calibration curve or a benchmark. The two tools with real user bases (Superpower, AI Toolbox) are manual or rule-based.

### C. Research and datasets

**Multi-session memory benchmarks test recall, not grouping.** Multi-Session Chat (Xu, Szlam, Weston, 2021) is human–human crowdworker chat over up to five sessions of up to 14 utterances, with gaps of 1–7 hours or 1–7 days and annotated summaries; training has 4,000 three-session and 1,001 four-session episodes; retrieval- and summary-augmented models beat plain encoder-decoders [35][36]. It ships inside ParlAI (code MIT; dataset licence not stated on the project page) [36][37]. LoCoMo (Maharana et al., February 2024) is generated by LLM agents with personas and temporal event graphs, then edited by people; about 300 turns and 9K tokens per conversation over up to 35 sessions; tasks are QA, event summarisation and multimodal dialogue; the arXiv paper is CC BY-NC-SA 4.0 and the repository's LICENSE.txt is CC BY-NC 4.0, non-commercial either way; the repository holds 10 conversations [38][39]. LongMemEval (Wu et al., ICLR 2025) has 500 questions over histories assembled from user attributes, evidence statements, filler sessions from ShareGPT and UltraChat, and simulated sessions; it tests information extraction, multi-session reasoning, temporal reasoning, knowledge updates and abstention; commercial assistants drop about 30% accuracy; MIT [40][42]. Mem0 (April 2025) extracts, consolidates and retrieves memories, reports a 26% relative gain over OpenAI's memory on LoCoMo with 91% lower p95 latency, and is Apache-2.0 with 67.3k stars [41][43]. None of these asks "which of this person's groups does a new chat belong to". Their one transferable idea is LongMemEval's abstention ability, which is Bundle's "none".

**Conversation clustering is done at the organisation level, offline.** Anthropic's Clio (December 2024) summarises each conversation into facets, embeds them with Sentence-BERT-style models, clusters with k-means, has a model name each cluster, builds a hierarchy with more k-means and prompting, and drops clusters below a minimum number of unique accounts and conversations (the numbers are left to appendices not opened today); it ran on one million claude.ai conversations and found web and mobile application development on top at over 10%, with education, business strategy, writing and research next [44][45]. LMSYS-Chat-1M (one million conversations from 210,000 IPs across 25 models) is gated on Hugging Face under its own agreement: no redistribution, and the licence can be ended at any time [46][47]. WildChat-1M (ICLR 2024; one million opt-in ChatGPT conversations) is listed as ODC-BY on its Hugging Face card, though the paper's abstract names AI2 ImpACT licences; 838k conversations in the train split [48][49]. ShareChat (December 2025, revised May 2026) has 142,808 publicly shared conversations from ChatGPT, Perplexity, Grok, Gemini and Claude in 95 languages, CC BY 4.0 [50]. A January 2026 paper clusters multi-turn support chats into concerns and refines clusters incrementally, splitting only degraded ones [51]. All of this groups many people's chats for analysts; nobody here groups one person's chats for that person.

**Topic segmentation is the within-conversation cousin.** TIAGE (Findings of EMNLP 2021) adds human topic-shift labels to PersonaChat [52]; SuperDialseg (EMNLP 2023) derives 9,478 segmented dialogues from document-grounded corpora and shows supervised segmentation is far ahead in-domain [53]; a December 2025 paper argues boundary F1 is tied to boundary density and that threshold sweeps move W-F1 more than switching methods do [54]. Lesson for Bundle's later "is this a follow-up?" question: judge pairs, not boundaries.

**The closest research framing is open intent discovery plus out-of-scope detection.** DSTC11 Track 2 (2023) gave three customer-service corpora (insurance 948 conversations with 22 intents; banking 1,000 with 29; finance 2,000 with 39), an intent-clustering task scored by ACC, NMI and ARI, and an open-induction task; the Task 1 baseline, all-mpnet-base-v2 sentence embeddings plus k-means, scored 55.8 ACC (rank 23 of 34), while the best Task 1 team reached 69.8 and the top eight sat between 66 and 70, mostly by fine-tuning sentence-transformers encoders (all-mpnet-base-v2, all-roberta-large, DSE RoBERTa) with SCCL, some with HDBSCAN; the Task 2 open-induction scores (top 76.3) are a different task and must not be mixed in; the repository holding code and data is Apache-2.0, with no separate data licence stated [55][56][57]. CLINC150 (EMNLP-IJCNLP 2019) has 150 intents across 10 domains with 100/20/30 examples each, plus 100 training, 100 validation and 1,000 test out-of-scope queries, and showed that classifiers that do well in-scope "struggle to identify out-of-scope queries"; CC BY 3.0 [58][59]. Banking77 (10,003 train, 3,080 test, 77 intents) is CC BY 4.0 [60]. Adaptive Decision Boundary (AAAI 2021) learns a sphere per known class from known-class data only, so unknowns fall outside [61]. Conversation disentanglement (ACL 2019; 77,563 annotated IRC messages) is the same "which thread, or a new one" decision on a message stream [62].

**The oldest and most honest precedent is email foldering.** Bekkerman, McCallum and Huang's UMass technical report benchmarked foldering on Enron and SRI mail with MaxEnt, Naive Bayes, SVM and Winnow, using an incremental time-based split (train on the first N messages, test on the next N, and so on) and ignoring test messages whose folder did not yet exist at training time; accuracy was below 70% in nine of fourteen cases, and the authors note that people create folders and let others fall out of use [63]. Gmail Priority Inbox (Google, 2010) ranks mail by a per-user model with a per-user threshold; when a person marks mail consistently in one direction the threshold is nudged in real time; on user-marked mail the error rate fell from 45% (global model) to 38% (per-user models) to 31% (per-user models and thresholds), and users spent 6% less time reading mail [64]. This is the design pattern Bundle is re-creating for chats: a personal label set that changes over time, a confidence threshold, and corrections that tune it.

## Options compared

| Approach | Who does it | Signal read | Runs where | Person's own bundles as labels | Explicit "none" | Probabilities, calibrated | Public measurement | Openness |
|---|---|---|---|---|---|---|---|---|
| Manual containers + memory + search + pin | ChatGPT, Claude, Gemini, Grok [1–17] | none (person decides) | their servers | yes | n/a | no | none | closed |
| Content-aware nudge to a fixed destination | ChatGPT Health suggestion [3] | message content | OpenAI servers | no (one fixed space) | implicit | not shown | none | closed |
| Keyword rules / title tags | AI Toolbox Smart Tags, Chat Organizer, Folderizr [22][23][33] | title, keywords | browser | partly (custom rules) | no | no | none | mixed; Folderizr GPL-3.0 |
| Cloud LLM reads titles | ChatFolders premium, Chat Organizer "ambiguous" path [23][24] | title only | third-party API | yes (suggests folders) | unclear | no | none | user's API key; model unknown |
| Offline clustering of many people's chats | Clio, LMSYS, lifecycle clustering [44][46][51] | full conversation | provider servers | no (global clusters) | no | no | papers | research only |
| Memory layer | ChatGPT/Claude/Gemini/Grok memory, Mem0 [3][8][12][14][41] | conversation facts | servers (Mem0 can self-host) | no | abstention in LongMemEval | no | LoCoMo, LongMemEval | Mem0 Apache-2.0 |
| Open intent clustering / OOS detection | DSTC11, CLINC150, ADB [55][58][61] | utterance | anywhere | per dataset, not per person | yes (OOS) | partly | yes, academic | Apache-2.0 / CC BY |
| Email foldering with per-user threshold | Bekkerman et al.; Gmail Priority Inbox [63][64] | message | server | yes | implicit | ranking + threshold | yes, 2004–2010 | papers |
| **Bundle (proposed)** | this project | chat text + candidate bundles | browser (Transformers.js) | yes, dynamic set | yes | yes, measured ECE/Brier | sealed exam, public board | Apache-2.0 / CC BY 4.0 |

## Recommendation

Keep the product. Nothing opened today files a person's chats into their own bundles automatically, in the browser, with a calibrated probability and an honest "none", and nothing publishes a measurement of doing so. That gap is real on 16 October 2026, and OpenAI has confirmed the request is open with no timeline [4].

Describe it honestly. Bundle is email foldering [63][64] re-done for chats with open intent discovery and out-of-scope detection [55][58][61] as the modelling frame, run on-device. Say so in the README and the tech view, and cite the lineage; it strengthens the "open proposal any platform can adopt" story rather than weakening it. Do not call folders, projects or memory new, and do not compare Bundle to LoCoMo-style memory benchmarks: they test recall, not grouping.

Borrow four things from the prior art: (1) a time-ordered exam inside each invented person, where a chat is scored only against the bundles that existed when it arrived, and a chat whose bundle does not exist yet counts as "none" (Bekkerman's rule) [63]; (2) out-of-scope test queries written deliberately, as CLINC150 (CC BY 3.0) did, not just left over [58][59]; (3) per-person threshold nudging from corrections as a platform recommendation, since Gmail's per-user thresholds cut error from 38% to 31% [64]; the demo itself keeps fixed, published cut-offs (D2 forbids storing anything about visitors); (4) ACC/NMI/ARI from DSTC11 (Apache-2.0) as secondary metrics so Bundle's board can be read by that community [55][57]. Nothing here recommends a gated or non-commercial artefact: LMSYS-Chat-1M (gated) and LoCoMo (CC BY-NC) are named only to be ruled out.

The baseline the relay already has (B1, a sentence encoder without training) is the right one: DSTC11's all-mpnet-base-v2 (Apache-2.0, not gated, 0.1B parameters, 768-dimensional [65]) plus k-means baseline at 55.8 ACC versus 69.8 for the best fine-tuned entry is the size of gain a student should show, about 14 points on that task [55].

## What doesn't work, or would change the plan

1. **The spec's line that "most people never do" set up projects is unverified.** No source found today measures it. Soften to "need to be set up by hand" until there is evidence.
2. **Memory benchmarks are not comparators.** MSC, LoCoMo, LongMemEval and Mem0 measure recall across sessions [35][38][40][41]. Any sentence in README or the tech view implying Bundle competes on them would be wrong. Use CLINC150-style OOS metrics and DSTC11 clustering metrics instead.
3. **Split by person is necessary but not sufficient.** The foldering literature shows the hard part is time: folders appear and die, and a test item may belong to a folder that does not exist yet [63]. The `tasks` and `exam` modules must build candidates from the person's state at that moment and label such chats "none"; the exam should report accuracy as a function of how many chats the person already has, as Bekkerman did.
4. **The "none" class needs its own precision and recall, and deliberate OOS writing.** CLINC150's finding is that in-scope accuracy says little about out-of-scope behaviour [58]. The relay's metrics list already has precision and recall for "none"; make the teacher write out-of-scope chats on purpose, including near-misses (a running question that is not about the Running bundle).
5. **Fixed global cut-offs leave gains behind.** Gmail's per-user thresholds mattered more than per-user models [64]. For the demo, fixed cut-offs are right (D2). For platform adopters, document a per-person threshold rule as part of the proposal.
6. **The window is narrowing on the product side.** ChatGPT's Health nudge (January 2026), Space (September 2026) and the open support ticket (September 2026) [3][4] say OpenAI can ship a closed version at any time. The durable differentiator is the open model, the open dataset and the public exam, not the feature. Prioritise the scoreboard and the release over demo polish if time is short.
7. **Real-chat datasets cannot feed the pipeline, and mostly should not.** LMSYS-Chat-1M is gated and non-redistributable [47], so a CC BY 4.0 dataset cannot derive from it. WildChat (ODC-BY on the Hugging Face card, AI2 ImpACT in the paper, so check before any use) [48][49] and ShareChat (CC BY 4.0) [50] are open but D3 rules out real chats for lessons and exams. One open point for Hrishikesh: a one-off, never-published realism check of the sealed exam's difficulty against ShareChat titles would be informative; it also cuts against the spirit of "never real chats", so it needs a decision, not a default.
8. **Topic-segmentation metrics are a trap for the follow-up question.** Boundary F1 moves more with thresholds than with methods [54]. If the "is this a follow-up?" toy lands, score it as pairwise classification.
9. **Comparison tables will date fast.** Gems become "skills" from November 2026 [11]; ChatGPT's Library became Space in September 2026 [3]. Any product comparison shipped on the site needs a "checked on" date and a plan to refresh it.
10. **Extensions already own the browser-sidebar niche.** Superpower (100,000 users) and AI Toolbox (40,000+) [18][20] are where people who want folders go. The spec's choice not to be an extension is right; competing there would mean scraping four changing DOMs, which is exactly what the small manual extensions struggle with.

## Sources

1. https://help.openai.com/en/articles/10169521-projects-in-chatgpt — Projects in ChatGPT, "Updated: 26 days ago" (checked 16 Oct 2026)
2. https://help.openai.com/en/articles/10056348-finding-your-chats-projects-and-files-in-chatgpt — sidebar search (checked 16 Oct 2026)
3. https://help.openai.com/en/articles/6825453-chatgpt-release-notes — ChatGPT release notes, latest entry 15 Oct 2026 (checked 16 Oct 2026)
4. https://community.openai.com/t/id-like-chatgpt-to-automatically-organize-my-conversations-projects-based-on-the-actual-content-of-each-chat/1388895/2 — OpenAI Support reply, 6 Sep 2026 (checked 16 Oct 2026)
5. https://techcrunch.com/?p=2931159 — TechCrunch on the Projects launch, 13 Dec 2024 (checked 16 Oct 2026)
6. https://support.claude.com/en/articles/9519177-how-can-i-create-and-manage-projects (checked 16 Oct 2026)
7. https://support.claude.com/en/articles/9517075-what-are-projects (checked 16 Oct 2026)
8. https://support.claude.com/en/articles/11817273-how-does-claude-s-memory-work (checked 16 Oct 2026)
9. https://support.claude.com/en/articles/12138966-release-notes — latest entry 7 Oct 2026 (checked 16 Oct 2026)
10. https://support.google.com/gemini/answer/13666746?hl=en — Find and manage your recent chats (checked 16 Oct 2026)
11. https://support.google.com/gemini/answer/15146780?hl=en&co=GENIE.Platform%3DDesktop — Use Gems (checked 16 Oct 2026)
12. https://support.google.com/gemini/answer/16598469?hl=en&co=GENIE.Platform%3DDesktop — memory of past chats (checked 16 Oct 2026)
13. https://grok.com/project — public tagline only; sign-in required (checked 16 Oct 2026)
14. https://grok.com/release-notes/aug-15-2026 — Grok release notes, 15 Aug 2026 (checked 16 Oct 2026)
15. https://docs.x.ai/grok/user-guide — Grok Business user guide (checked 16 Oct 2026)
16. https://techcrunch.com/2025/04/16/xai-adds-a-memory-feature-to-grok — 16 Apr 2025 (checked 16 Oct 2026)
17. https://www.maginative.com/article/xai-upgrades-grok-with-personalized-memory-and-custom-workspaces/ — 17 Apr 2025 (checked 16 Oct 2026)
18. https://chromewebstore.google.com/detail/superpower-chatgpt/amhmeenmapldpjdedekalnfifgnpfnkc (checked 16 Oct 2026)
19. https://github.com/saeedezzati/superpower-chatgpt (checked 16 Oct 2026)
20. https://www.ai-toolbox.co/chatgpt-management-and-productivity/organizing-chats-with-folders-chatgpt-toolbox (checked 16 Oct 2026)
21. https://www.ai-toolbox.co/ — vendor home page; seen in search listings only, not opened today, not relied on
22. https://www.ai-toolbox.co/ai-toolbox-chatgpt-features/chatgpt-smart-tags-auto-organize-2026 — Smart Tags, updated 24 Jun 2026 (checked 16 Oct 2026)
23. https://chat-organizer.com/how-to-organize-chatgpt-chats.html (checked 16 Oct 2026)
24. https://www.chatfolders.dev/ (checked 16 Oct 2026)
25. https://chromewebstore.google.com/detail/chatfolders-organize-chat/gmodioghihgkkmeldhfhgencclmmmjib?hl=en (checked 16 Oct 2026)
26. https://chromewebstore.google.com/detail/chatgpt-organizer-smart-a/fifjakginaannmjjejmfagoglkiocbco (checked 16 Oct 2026)
27. https://aichatnavigator.com/ (checked 16 Oct 2026)
28. https://sortbase.ai/ (checked 16 Oct 2026)
29. https://chromewebstore.google.com/detail/ai-chat-organizer/njbpjlfmnfbpanklbbhmpljanhiccodg?hl=en (checked 16 Oct 2026)
30. https://chromewebstore.google.com/detail/chatgpt-folders-search-bo/ibelppoiheipgceppgklepmjcafbdcdm (checked 16 Oct 2026)
31. https://chromewebstore.google.com/detail/chatgpt-folders-organize/gkdckjppoonjgnibgmkmclednhhicfbl (checked 16 Oct 2026)
32. https://www.llmnesia.com/blog/how-to-organize-claude-conversation-history — 23 Apr 2026 (checked 16 Oct 2026)
33. https://github.com/trincio/ChatGPT-Folderizr (checked 16 Oct 2026)
34. https://github.com/huangzf128/AIChatFolders (checked 16 Oct 2026)
35. https://arxiv.org/abs/2107.07567 — Beyond Goldfish Memory (MSC), 2021 (checked 16 Oct 2026)
36. https://arxiv.org/pdf/2107.07567 — MSC paper PDF, Tables 1–2 and section on session lengths (checked 16 Oct 2026)
37. https://parl.ai/projects/msc/ and https://github.com/facebookresearch/ParlAI — distribution and MIT code licence (checked 16 Oct 2026)
38. https://arxiv.org/abs/2402.17753 — LoCoMo paper; arXiv listing shows CC BY-NC-SA 4.0 (checked 16 Oct 2026)
39. https://github.com/snap-research/locomo — LICENSE.txt is CC BY-NC 4.0; data/locomo10.json (checked 16 Oct 2026)
40. https://arxiv.org/abs/2410.10813 — LongMemEval, ICLR 2025 (checked 16 Oct 2026)
41. https://github.com/mem0ai/mem0 — Apache-2.0, 67.3k stars (checked 16 Oct 2026)
42. https://github.com/xiaowu0162/longmemeval — MIT; history construction (checked 16 Oct 2026)
43. https://arxiv.org/abs/2504.19413 — Mem0 paper, 28 Apr 2025 (checked 16 Oct 2026)
44. https://arxiv.org/html/2412.13678 — Clio paper, method details (checked 16 Oct 2026)
45. https://www.anthropic.com/research/clio — Clio announcement, 12 Dec 2024 (checked 16 Oct 2026)
46. https://arxiv.org/abs/2309.11998 — LMSYS-Chat-1M (checked 16 Oct 2026)
47. https://huggingface.co/datasets/lmsys/lmsys-chat-1m — gated; dataset licence agreement (checked 16 Oct 2026)
48. https://arxiv.org/abs/2405.01470 — WildChat, ICLR 2024; abstract names AI2 ImpACT licences (checked 16 Oct 2026)
49. https://huggingface.co/datasets/allenai/WildChat-1M — ODC-BY (checked 16 Oct 2026)
50. https://arxiv.org/abs/2512.17843 — ShareChat, CC BY 4.0 (checked 16 Oct 2026)
51. https://arxiv.org/abs/2601.04388 — lifecycle-aware clustering of support chats, AACL 2025 (checked 16 Oct 2026)
52. https://aclanthology.org/2021.findings-emnlp.145/ — TIAGE (checked 16 Oct 2026)
53. https://arxiv.org/abs/2305.08371 — SuperDialseg, EMNLP 2023 (checked 16 Oct 2026)
54. https://arxiv.org/abs/2512.17083 — When F1 Fails, Dec 2025 (checked 16 Oct 2026)
55. https://aclanthology.org/2023.dstc-1.27.pdf — DSTC11 Track 2 paper; Table 2 (data), Table 3 (Task 1 and Task 2 results), Table 5 (Task 2 encoders) (checked 16 Oct 2026)
56. https://arxiv.org/abs/2304.12982 — DSTC11 Track 2 abstract (checked 16 Oct 2026)
57. https://github.com/amazon-science/dstc11-track2-intent-induction — Apache-2.0 code and data (checked 16 Oct 2026)
58. https://arxiv.org/abs/1909.02027 — CLINC150 / OOS, EMNLP-IJCNLP 2019 (checked 16 Oct 2026)
59. https://github.com/clinc/oos-eval and its LICENSE — counts; CC BY 3.0 (checked 16 Oct 2026)
60. https://github.com/PolyAI-LDN/task-specific-datasets — Banking77, CC BY 4.0 (checked 16 Oct 2026)
61. https://arxiv.org/abs/2012.10209 — Adaptive Decision Boundary, AAAI 2021 (checked 16 Oct 2026)
62. https://arxiv.org/abs/1810.11118 — conversation disentanglement corpus, ACL 2019 (checked 16 Oct 2026)
63. https://people.cs.umass.edu/~mccallum/papers/foldering-tr05.pdf — Bekkerman, McCallum, Huang, UMass CIIR TR IR-418 (checked 16 Oct 2026)
64. https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/36955.pdf — The Learning Behind Gmail Priority Inbox, 2010 (checked 16 Oct 2026)
65. https://huggingface.co/sentence-transformers/all-mpnet-base-v2 — model card: Apache-2.0, not gated, 0.1B parameters, 768-dimensional (checked 16 Oct 2026)

Not opened today, seen only in search listings and therefore not relied on: aloktripathi1/chatgpt-organizer, glyndavidson/chatgpt-folders, Tech127x/chatgpt-folders, bujue3709/GPT-Conversation-Toolkit, Perplexity Spaces, Le Chat and Copilot organisation features.

## Verification notes (skeptic)

Second pass on 16 October 2026 by the R5 skeptic. Every source named below was reopened today. help.openai.com refused plain fetches (HTTP 403) and was read through a real browser; the three PDFs [55][63][64] and the MSC and TIAGE PDFs were downloaded and their text extracted.

Confirmed as written:
- [47] LMSYS-Chat-1M is gated under its own agreement, forbids transfer to third parties and can be ended at any time; 1,000,000 conversations, 25 models, 210,479 IPs.
- [49] WildChat-1M card: ODC-BY, 838k train rows. [39] LoCoMo repository holds data/locomo10.json, ten conversations.
- [41][43] Mem0 Apache-2.0, 67.3k stars; the paper abstract has the 26% relative gain over OpenAI memory on LoCoMo and 91% lower p95 latency. The README today shows a newer algorithm's figures (92.5 on LoCoMo), not the paper's.
- [59] CLINC150 LICENSE is CC BY 3.0 Unported; 150 intents, 100/20/30 per intent, 100/100/1,000 out-of-scope. [58] the "struggle to identify out-of-scope queries" line is in the abstract.
- [60] Banking77 CC BY 4.0, 10,003 train, 3,080 test, 77 intents.
- [18][19] Superpower: 100,000 users, 4.6 from 3.7K ratings, updated 16 Oct 2026; 1.7k stars; custom licence forbidding redistribution, commercial use and reuse of the source.
- [50] ShareChat 142,808 conversations, 660,293 turns, 95 languages, CC BY 4.0; v1 19 Dec 2025, v4 17 May 2026.
- [4] OpenAI Support, 6 Sep 2026: "No timeline to share yet."
- [64] Gmail Priority Inbox PDF: 45% global, 38% per-user, 31% per-user plus thresholds; real-time threshold increment on consistent marking; 6% less time reading mail; 2010.
- [63] Bekkerman, McCallum, Huang, UMass CIIR TR IR-418: Enron and SRI; MaxEnt, Naive Bayes, SVM, Winnow; incremental time-based split with N=100 (Enron) and N=50 (SRI); test messages in folders absent from training are ignored; "in nine of fourteen cases they are below 70%"; folders "fall out of use".
- [36] MSC PDF: 4,000 three-session and 1,001 four-session training episodes; up to 14 utterances a session; gaps of 1–7 hours or 1–7 days. [37] the project page states no dataset licence.
- [3] ChatGPT release notes, read in a browser: 18 Dec 2025 pinned chats; 7 Jan 2026 Health, with the sentence that a health question in a regular chat may get a suggestion to continue in Health; 5 May, 4 Jun and 12 Jun 2026 memory entries; 18 Jun 2026 pinning; 14 Jul 2026 search; 16 Jul 2026 Unified Recents; 7 Aug 2026 search includes folders; 29 Sep 2026 Space replaces Library for accounts with access; latest entry 15 Oct 2026.
- [1] Projects page: drag or "Move to project"; GPT chats cannot be moved; inherits instructions and files; "Remove from project"; Free 5 files and 5 collaborators, Plus and Go 25 and 10, Pro 40 and 100; default or project-only memory, changeable later; shared projects always project-only; "Updated: 26 days ago". The 14 Aug 2026 date for the memory switch rests on that day's release-notes heading ("Learning, Projects, and personalized suggestions") and was not re-read in full.
- [6][7][8][9] Claude: "Add to project", move between or remove, star, five projects on free accounts, per-project memory, search on paid plans, parallel-threads beta; release notes latest 7 Oct 2026 with the four dated entries (11 Aug 2025, 11 Sep 2025, 10 Jul 2026, 25 Aug 2026) and nothing on pinning or grouping.
- [10][11][12] Gemini: pin, unpin, rename, delete, search, branch, and asking about past chats by topic or timeframe; Gems become skills from November 2026; Memory needs 18+, a personal account and Keep Activity, and is not in Gems or Live.
- [14] Grok 15 Aug 2026 notes, read from the page's embedded data: voice in project conversations; project icons with pagination; the share dialog says sharing a project includes its conversations; chat history in sync across tabs; selectable memory summary. [15][16][17] as written.
- [20][22][23][24][25][26][27][32][33][34] extension facts as written, including AI Toolbox storing folders with an AI Toolbox account, ChatFolders' prices and own-key cloud categoriser, Chat Organizer's wordlist plus shared AI service on titles, AI Chat Navigator's grouping as Planned, Folderizr GPL-3.0 with 2 stars, AIChatFolders MIT with 0 stars.
- [40][42] LongMemEval: 500 questions, five abilities, 30% drop, ICLR 2025; code MIT. [44][45] Clio 12 Dec 2024, one million conversations, k-means and prompting. [52] TIAGE augments PersonaChat (paper PDF). [53] 9,478 dialogues. [62] 77,563 messages. [61] AAAI 2021, spherical boundaries from known classes only. [51] AACL 2025, submitted 7 Jan 2026. [54] Dec 2025. [57] Apache-2.0. [65] all-mpnet-base-v2 Apache-2.0, not gated.

Fixed in place:
1. DSTC11 numbers conflated two tasks. The 55.8 baseline is Task 1 (intent clustering) ACC, rank 23 of 34; the best Task 1 entry scored 69.8, not "about 72"; the 72–76 figures the draft quoted are Task 2 (open intent induction), Tables 3 and 5. Section C and the Recommendation now say 55.8 versus 69.8, about 14 points. This also shrinks the gain a student should be expected to show.
2. LoCoMo licence: the arXiv paper is CC BY-NC-SA 4.0 but the repository's LICENSE.txt is CC BY-NC 4.0; the draft gave only the former. Both now stated; non-commercial either way.
3. The Claude memory help page does not "state plainly" that memory does not group chats; it is silent. Reworded.
4. "Up to eight recent conversations" is dated 21 August 2026 in the release notes, not 20 August (20 August is pinned-chat sync between desktop and iOS).
5. Clio's top categories were "coding, writing and research"; the announcement says web and mobile app development over 10%, then education and business strategy. Corrected.
6. WildChat: the Hugging Face card says ODC-BY but the paper's abstract names AI2 ImpACT licences; both now noted and item 7 carries a check-before-use flag.
7. DSTC11 "code and data Apache-2.0" softened: the repository is Apache-2.0 and no separate data licence is stated.
8. Sortbase "formerly Easy Folders" is not on the page opened; marked NOT VERIFIED.
9. TechCrunch's wording on Projects turned into a paraphrase rather than attributed words.
10. Licences added where the recommendation leans on an artefact: CLINC150 CC BY 3.0, DSTC11 Apache-2.0, all-mpnet-base-v2 Apache-2.0 (new source [65]), with an explicit line that nothing gated or non-commercial is recommended.
11. The 18 June 2026 release note also lets Recents be grouped by project; added, labelled a view rather than a sorter.

Not re-checked today: [2] (403 and not opened in the browser), [13], [21], [29][30][31], [35] and [46] beyond their abstracts, [28] beyond prices, account count and company location, [5] beyond its date and plans. Quotes were counted: none is 15 words or longer.
