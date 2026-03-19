# artok demo - Arabic Token Tax Calculator
# Run: vhs demo.tape

Output demo.gif
Set Shell "zsh"
Set FontSize 14
Set Width 1200
Set Height 800
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms
Set Padding 20

# Activate venv
Hide
Type "source .venv/bin/activate && clear"
Enter
Sleep 500ms
Show

# --- Scene 1: Basic comparison ---
Sleep 500ms
Type 'artok "الذكاء الاصطناعي يغير العالم" -e "AI is changing the world"'
Sleep 500ms
Enter
Sleep 5s

# --- Scene 2: Token visualization ---
Type 'artok "مرحبا بالعالم العربي" --viz gpt4o,claude-sonnet'
Sleep 500ms
Enter
Sleep 6s

# --- Scene 3: Cost estimate ---
Type 'artok "نص عربي طويل للاختبار" -e "Long Arabic text for testing" --cost 50'
Sleep 500ms
Enter
Sleep 5s

# --- Scene 4: Budget recommendation ---
Type 'artok "الذكاء الاصطناعي" --recommend 100 --words 5'
Sleep 500ms
Enter
Sleep 5s

# --- Scene 5: Chart ---
Type 'artok "بسم الله الرحمن الرحيم" -e "In the name of God" --chart'
Sleep 500ms
Enter
Sleep 5s

Sleep 2s
