# Socrates-AI
LLM dialogues with eachother  to find better solutions
# 🏛️ Σωκρατικός Διάλογος Pro — Agentic AI Lab

Μια advanced, single-file (`.html`) εφαρμογή εξομοίωσης αυτόνομων πρακτόρων (Multi-Agent Engine) που αναπαράγει τον κλασικό Σωκρατικό Έλεγχο και τη Μαιευτική Μέθοδο, χρησιμοποιώντας τα κορυφαία LLMs της αγοράς (Claude, Grok, Gemini, GPT-4o) σε ένα δυναμικό, φιλοσοφικό debate.

---

## 🚀 Το Τελικό Feature Set (Agentic Architecture)

Η εφαρμογή ξεφεύγει από τα όρια ενός απλού chat interface και ενσωματώνει 11 αυτόνομες μηχανές (Engines) που τρέχουν παράλληλα:

* **✅ Memory Engine & Consensus Memory:** Κρατάει δυναμικό, κοινό μητρώο με τα αξιώματα και τα συμπεράσματα στα οποία συμφωνούν οι πράκτορες κατά τη διάρκεια του διαλόγου.
* **✅ Contradiction Graph & Knowledge Graph:** Τα μοντέλα αναλύουν τις προηγούμενες τοποθετήσεις, εντοπίζουν λογικά κενά και χαρτογραφούν live τις αντιφάσεις στο αντίστοιχο UI Graph Component.
* **✅ Reflection Loop & Tree of Thought:** Πριν από κάθε επίσημη απάντηση, το AI εκτελεί έναν εσωτερικό κύκλο αυτοκριτικής και ανάλυσης πολλαπλών μονοπατιών σκέψης.
* **✅ Live Reasoning Timeline:** Κάθε turn περιλαμβάνει ένα collapsible panel όπου ο χρήστης βλέπει σε πραγματικό χρόνο το "thought process" του μοντέλου πριν αυτό καταλήξει στην τελική του απάντηση.
* **✅ Advanced Reputation System:** Ένα εξελιγμένο scoreboard που βαθμολογεί live κάθε AI πράκτορα σε 3 άξονες: *Διαλεκτική Ικανότητα*, *Λογική Δομή* και *Ευελιξία (Χρυσός Κανόνας)*.
* **✅ Evolution Engine (Ο Χρυσός Κανόνας):** Ρητή prompt-driven οδηγία που αναγκάζει τα AI να "ρίξουν το εγώ τους", να αποδεχτούν τις εύστοχες σωκρατικές ερωτήσεις και να εξελίξουν τη θεωρία τους αντί να αμύνονται πεισματικά.
* **✅ Automatic Fact Checker & Source Manager (Human-in-the-Loop):** Ειδική μπάρα παρέμβασης στο κάτω μέρος της οθόνης, η οποία επιτρέπει στον χρήστη να εισάγει δεδομένα, πηγές ή ενστάσεις τις οποίες τα AI αναγκάζονται να επεξεργαστούν στον επόμενο γύρο.

---

## 🛠️ Τεχνική Επίλυση Προκλήσεων (Architecture Patches)

* **Multi-Agent Conversation Crash Fixed:** Οι περισσότερες APIs (OpenAI, Anthropic) επιστρέφουν `400 Bad Request` αν εντοπίσουν διαδοχικά μηνύματα από το ίδιο role (π.χ. assistant-assistant). Η εφαρμογή χρησιμοποιεί τον *Integral Prompt Injector* (`buildMsgs`), ο οποίος μεταμφιέζει δυναμικά όλους τους *άλλους* AI πράκτορες σε `user` για το τρέχον μοντέλο, εξασφαλίζοντας 100% σταθερότητα.
* **Unified LLM API Engine:** Πλήρης, native υποστήριξη για τα custom headers και τις ιδιαιτερότητες του Anthropic API (Claude), του Google AI API (Gemini) και της OpenAI αρχιτεκτονικής (ChatGPT, Grok).

---

## 📦 Εγκατάσταση και Χρήση

Η εφαρμογή είναι **zero-install** και **serverless**. Όλη η λογική τρέχει direct στον browser σου.

1. Κατέβασε το αρχείο `socratic-pro.html`.
2. Άνοιξέ το με οποιονδήποτε σύγχρονο browser (Chrome, Edge, Firefox, Safari).
3. Εισήγαγε τα API Keys σου στο ειδικό panel (αποθηκεύονται μόνο τοπικά στη μνήμη του session).
4. Γράψε το φιλοσοφικό ζήτημα που θες να ερευνηθεί, επίλεξε τους γύρους και πάτα **Activation**.

---

## 📥 Export Capability

Με το πέρας του διαλόγου, μπορείς να πατήσεις το κουμπί **Export Markdown** για να λάβεις ένα πλήρες, δομημένο report της φιλοσοφικής έρευνας, το οποίο περιλαμβάνει:
* Το τελικό Consensus Memory Graph.
* Τις καταγεγραμμένες λογικές αντιφάσεις.
* Ολόκληρο το ιστορικό του διαλόγου σε clean markdown μορφή.
