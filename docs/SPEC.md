# Bundle: product specification
v0.1 draft, 16 October 2026. Bundle is a working name; the public name is not settled.

## Problem
People who use AI chat apps for everyday questions build up long sidebars of disconnected chats. Each new chat starts from nothing. Related questions asked weeks apart, such as a training plan, a trip or a renovation, end up scattered among one-off questions. Finding an old chat, or carrying it on, means scrolling and guessing. Projects and memory features help the people who set them up by hand; most people never do.

## Who it is for
- Everyday users of any AI chat app who never organise their chats.
- Chat platforms that could offer automatic organisation to every user.
- Developers and researchers who want a small open decision model, and an honest benchmark, for this task.

## What Bundle is
1. The model: a small open decision model. Given a new chat and the person's existing bundles and loose chats, it returns a probability for each, plus one for "none of these". It never writes text, and it is small enough to run in a web browser.
2. The rules: file automatically when the model is very sure, suggest when it is fairly sure, otherwise leave the chat loose. The cut-offs come from measured calibration, so a stated 90% is right about nine times in ten.
3. The pipeline: an open-licensed teacher model writes invented people, their lives and their chats, with the correct bundle for each. The student model learns from these lessons; practice tests find its weak spots; and a sealed exam decides each release.
4. The scoreboard: every exam result is published. It compares the student with a no-training baseline, its previous version, an open general decision model and a frontier small model, on accuracy, honesty of percentages, speed, and size and cost.
5. The demo website: a playful personality quiz leads to a chat history written for someone like the visitor. They tap ready-made questions, months pass in seconds, and they are asked to find an old chat. One switch bundles everything, the chat turns up in seconds, and it carries on with its bundle's context. A layman view tells the story; a tech view shows the architecture, the live probabilities and the scoreboard.

## What it deliberately does not do
- Store anything about visitors (chats, quiz answers, accounts, cookies or analytics), or train on anything visitors do.
- Train on real people's chats, or copy text from the web.
- Write chat replies: the demo's replies are written in advance.
- Act as a chat app, a browser extension or a cross-app organiser.
- Use any company's branding, or imply endorsement by any AI provider.

## Look and feel
Playful and effortless at the front: taps, not typing, and a result that feels like a fun personality test. Precise and transparent in the tech view. Its own visual identity, not an imitation of any chat product. Phone first.

## How we will know it works
- The student beats the no-training baseline on the sealed exam, and the gap is published.
- Chats filed automatically are right at least 95% of the time on the exam (target).
- One decision takes well under a second in a mid-range phone browser, and the model finishes downloading while the quiz is being taken.
- In the demo, finding an old chat is much faster with bundles on.
- Each release beats the last on the exam or does not ship, and every result is public.
- By 31 December 2026, the model, its training data, the scoreboard history and the demo are released under open licences.

## Licences
Code Apache-2.0. Documentation and datasets CC BY 4.0. Model weights Apache-2.0, which requires an Apache-2.0 or MIT base model.
