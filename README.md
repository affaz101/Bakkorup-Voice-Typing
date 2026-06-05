<div align="center">
  
# 🚀 Bakkorup Voice Typing Software for PC

**The Ultimate Offline Bengali Voice Typing & Banglish Transliteration App for Windows.**

![Status](https://img.shields.io/badge/Status-Exciting_Release!-success?style=for-the-badge) ![Platform](https://img.shields.io/badge/Platform-Windows-blue?style=for-the-badge) ![Language](https://img.shields.io/badge/Language-Bengali_&_Banglish-orange?style=for-the-badge) ![SEO](https://img.shields.io/badge/Offline-Speech_to_Text-purple?style=for-the-badge)

</div>

<br>
<br>

---

## 📖 Chapter 1: The Everyday Frustration

Imagine having to write a long Bengali report for the office or a lengthy, heartfelt Facebook post. You place your hands on the keyboard. If you're using traditional typing tools like Avro or Bijoy, it takes an enormous amount of time. Writing complex Bengali conjuncts (যুক্তাক্ষর) can quickly become frustrating. 

We often think: *"I wish there was a tool where I could just speak, and my PC would type it out automatically!"*

Yes, there are voice typing tools on the internet. But almost all of them suffer from three massive flaws:
1. **High Latency:** You speak, and the text appears seconds later. It breaks your concentration.
2. **Internet Dependency:** If your internet drops or is slow, you can't type a single word.
3. **Severe Privacy Risks:** Your private voice data, confidential office chats, or personal stories are uploaded to third-party cloud servers to be processed.

Isn't there a better solution? A tool that is lightning-fast, works completely offline, and looks like a premium software?

<br>

---

## 💡 Chapter 2: The Birth of "Bakkorup"

To answer those exact questions, we created **Bakkorup (বাক্যরূপ)**!

We wanted to build a Bengali Speech-to-Text software that doesn't wait for cloud servers. A tool that acts as a mini-AI brain sitting directly *inside* your computer.

Whenever you speak into your microphone, this AI listens and instantly converts your voice to text. Better yet, it works seamlessly across your operating system. Whether your cursor is in Microsoft Word, Notepad, Google Chrome, or Facebook—it magically types out your words right there!

And the best part? Your data never leaves your computer. **100% Guaranteed Privacy.**

<br>

---

## 🧠 Chapter 3: How Does The Magic Work?

The secret behind Bakkorup's zero-latency, lightning-fast typing is its **Dual Engine Architecture**.

### 1. The Offline AI Engine (Local Power)
Bakkorup leverages one of the world's best streaming AI models: `sherpa-onnx`. This language model uses your PC's local hardware (CPU/RAM) to perform speech recognition. 
The first time you run the app, it automatically downloads a highly optimized, lightweight (60MB) language model. From then on, it is capable of transcribing Bengali voice to text forever—**without any internet connection!**

### 2. The Remote Cloud Engine (For Low-End PCs)
We understand that some older computers might struggle to run AI models locally. For them, we’ve included a **Remote Connection Mode**. 
You can easily connect the app to any high-performance WebSocket server. Bakkorup will securely stream your audio and bring back the text at blazing speeds!

<br>

---

## 🎨 Chapter 4: A Design That Catch The Eye

Desktop apps built with Python usually suffer from boring, outdated User Interfaces. We refused to compromise on design.

We wanted users to feel a sense of "Wow" the moment they open the app. Using `CustomTkinter`, we crafted a **Premium Glass-like Borderless Interface**.
*   **Borderless Magic:** We removed the default Windows title bar and built a custom dragging mechanism. You can smoothly drag the app anywhere on your screen.
*   **Day/Night Mode:** Love dark mode? Prefer light mode? Our color palettes are carefully curated by professional designers to be soothing to the eyes.

<br>

---

## ⌨️ Chapter 5: Bangla or Banglish? You Choose!

Bengali typists generally fall into two categories:
One group loves typing in pure Bengali script (e.g., "আমি বাংলায় গান গাই"). 
The other group is much more comfortable typing Bengali phonetically using an English keyboard (e.g., "ami banglay gan gai").

Bakkorup caters to both! The app features two distinct transliteration modes:
*   **Bangla Mode:** Speak normally, and it types perfectly in pure Bengali script. Ideal for professional and official documents.
*   **Banglish Mode:** This is our most loved feature! Speak in Bengali, and our internal phonetic parser (`bnbphoneticparser`) will instantly transliterate your words and type them out in English alphabets (Banglish) in real-time!

<br>

---

## 🦸 Chapter 6: The Unseen Hero (System Tray & Hotkeys)

A perfect desktop application shouldn't be a nuisance on your screen. 

Bakkorup is designed to be minimized straight into your **System Tray**. 
*   **Persistent Taskbar:** Despite being a borderless app, we utilized core Windows APIs (Win32 API) to forcefully pin it to the taskbar, making it behave like a true native application.
*   **Global Hotkeys:** You don't even need to touch your mouse! No matter what app you are currently using, just hit the global shortcuts:
    *   `Alt + V` ➔ Start or Stop listening instantly.
    *   `Alt + 1` ➔ Switch to pure Bengali (Bangla) typing mode.
    *   `Alt + 2` ➔ Switch to Banglish transliteration mode.

<br>

---

## 🚀 Chapter 7: How Can You Experience The Magic?

Using Bakkorup is so incredibly easy that anyone with basic computer knowledge can run it. We have divided our guide for two types of users:

### 👤 For Normal Users (Just Download & Run!)
You do NOT need to know coding, and you do NOT need to install Python. Just follow these 3 simple steps:
1. Go to the **Releases** section on the right side of this page.
2. Download the `BakkorupVoiceTyping.exe` file.
3. Double-click to open the file. (On its very first run, it will automatically download the offline AI model in the background).

That's it! Place your cursor in any text box and press `Alt + V` to start talking!

### 💻 For Geeks & Developers (Run from Source)
If you are a Python developer and want to experiment with our codebase, you are highly welcome!

1. Clone the repository:
```bash
git clone https://github.com/yourusername/Bakkorup-Voice-Typing.git
cd Bakkorup-Voice-Typing/local
```

2. Activate your virtual environment and install dependencies:
```bash
pip install -r requirements.txt
pip install sherpa-onnx
```

3. Run the main application to see the magic:
```bash
python gui.py
```

<br>

---

## 🔒 Chapter 8: A Promise of Privacy

Bakkorup never clutters your PC or steals your data.
*   **Zero Clutter:** No matter where you keep the `.exe` file, all your settings and AI models are securely saved in Windows' internal `%APPDATA%\BakkorupVoiceTyping` folder. Your software folder remains 100% clean.
*   **Zero Data Collection:** We do not store your voice data or text. Everything is processed in your RAM and instantly deleted.

<br>

---

## 🔮 Chapter 9: What's Next? (The Future)

We don't want to stop here. Our roadmap to making Bakkorup the greatest Bengali voice typing software includes:
- **Smart Punctuation:** Automatically inserting commas (,) and periods (।) by understanding the pauses in your speech.
- **Voice Commands:** Using commands like "New Paragraph" or "Delete All" to control your PC purely with your voice.
- **Micro-Animations:** Adding beautiful, dynamic audio waveform visualizers while you speak.

<br>

---

## 🤝 Chapter 10: Call to Action (Join the Community)

Bakkorup is just a small step toward advancing the Bengali language in the tech space. It is a completely **Open-Source** project.

We want the community to come together to make it even bigger and more accurate. 
If you want to add a new feature, improve the design, or fix a bug, please feel free to **Fork** the project and submit a **Pull Request (PR)**! 

For any ideas, discussions, or bug reports, let us know in the **Issues** tab.

<br>

---

## 📜 Chapter 11: License

This project is open to everyone and released under the [MIT License](https://choosealicense.com/licenses/mit/). 
This means you can use, modify, and redistribute this software for personal or commercial use completely free of charge!

<br>

---

<div align="center">
  <h3>A relentless effort to make our mother tongue easier through technology — <b>Bakkorup!</b></h3>
  <i>Made with ❤️ for the Bengali Community</i>
</div>
