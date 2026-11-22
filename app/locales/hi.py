"""Hindi (Devanagari). Keys are the English sentences used in the code."""

MESSAGES = {
    # ---- navigation ----
    "Dashboard": "डैशबोर्ड",
    "Account settings": "खाता सेटिंग्स",
    "Log out": "लॉग आउट",
    "Log in": "लॉग इन",
    "Sign up": "साइन अप",
    "Change language": "भाषा बदलें",
    "Account menu for {username}": "{username} का खाता मेनू",
    "Back to Link Shortener": "Link Shortener पर वापस जाएँ",
    # ---- home page ----
    "Short links with your name on them.": "आपके नाम वाले छोटे लिंक।",
    "Every account gets its own namespace, so {example} is always yours, even if someone else also picks {word}. Track clicks, expire links, export everything.":
        "हर खाते को अपना अलग नेमस्पेस मिलता है, इसलिए {example} हमेशा आपका रहता है, भले ही कोई और भी {word} चुन ले। क्लिक ट्रैक करें, लिंक की समय-सीमा तय करें, और सब कुछ एक्सपोर्ट करें।",
    "Create a free account": "मुफ़्त खाता बनाएँ",
    "Click analytics": "क्लिक एनालिटिक्स",
    "Daily clicks, devices and referrers for every link.": "हर लिंक के रोज़ के क्लिक, डिवाइस और रेफ़रर।",
    "QR codes": "QR कोड",
    "Download one QR code or a zip of all of them.": "एक QR कोड डाउनलोड करें या सभी की एक zip फ़ाइल।",
    "Your data": "आपका डेटा",
    "Export to CSV and delete links in bulk.": "CSV में एक्सपोर्ट करें और एक साथ कई लिंक हटाएँ।",
    # ---- log in / sign up ----
    "Username or email": "यूज़रनेम या ईमेल",
    "Password": "पासवर्ड",
    "New here?": "यहाँ नए हैं?",
    "Create an account": "खाता बनाएँ",
    "Create your account": "अपना खाता बनाएँ",
    "Username": "यूज़रनेम",
    "This becomes part of your short links: yoursite.com/{u}/alias":
        "यह आपके छोटे लिंक का हिस्सा बनेगा: yoursite.com/{u}/alias",
    "Email": "ईमेल",
    "At least 8 characters.": "कम से कम 8 अक्षर।",
    "Create account": "खाता बनाएँ",
    "Already registered?": "पहले से पंजीकृत हैं?",
    # ---- protected link / verify email ----
    "Protected link": "सुरक्षित लिंक",
    "This link is protected": "यह लिंक सुरक्षित है",
    "Enter the password you were given to continue.": "आगे बढ़ने के लिए आपको दिया गया पासवर्ड डालें।",
    "Continue": "आगे बढ़ें",
    "Verify email": "ईमेल सत्यापित करें",
    "Check your inbox": "अपना इनबॉक्स देखें",
    "We sent a 6-digit code to {email}. It expires in 10 minutes.":
        "हमने {email} पर 6 अंकों का कोड भेजा है। यह 10 मिनट में समाप्त हो जाएगा।",
    "Verification code": "सत्यापन कोड",
    "Verify and change email": "सत्यापित करें और ईमेल बदलें",
    "Send a new code": "नया कोड भेजें",
    "Cancel": "रद्द करें",
    # ---- dashboard ----
    "Your links": "आपके लिंक",
    "{n} link": "{n} लिंक",
    "{n} links": "{n} लिंक",
    "{n} total click": "कुल {n} क्लिक",
    "{n} total clicks": "कुल {n} क्लिक",
    "Long URL": "लंबा URL",
    "Custom alias": "कस्टम नाम",
    "(optional)": "(वैकल्पिक)",
    "optional": "वैकल्पिक",
    "Shorten": "छोटा करें",
    "Starts at": "शुरू होने का समय",
    "Ends at": "समाप्त होने का समय",
    "Visitors must enter it": "आने वालों को इसे डालना होगा",
    "Times use your local time. Leave a box empty for no limit.":
        "समय आपके स्थानीय समय में हैं। कोई सीमा न चाहें तो खाना खाली छोड़ें।",
    "Delete the selected links? This cannot be undone.": "चुने हुए लिंक हटाएँ? इसे वापस नहीं किया जा सकता।",
    "Delete selected": "चुने हुए हटाएँ",
    "Download QR codes": "QR कोड डाउनलोड करें",
    "Export CSV": "CSV एक्सपोर्ट करें",
    "QR download uses the selected links, or all links if none are selected.":
        "QR डाउनलोड चुने हुए लिंक के लिए होता है, और कुछ न चुनें तो सभी लिंक के लिए।",
    "Select all links": "सभी लिंक चुनें",
    "Short link": "छोटा लिंक",
    "Destination": "गंतव्य",
    "Clicks": "क्लिक",
    "QR": "QR",
    "Status": "स्थिति",
    "Select {slug}": "{slug} चुनें",
    "Visitors need a password": "आने वालों को पासवर्ड चाहिए",
    "Download QR code": "QR कोड डाउनलोड करें",
    "Download QR code for {slug}": "{slug} के लिए QR कोड डाउनलोड करें",
    "Active": "चालू",
    "Scheduled": "निर्धारित",
    "Expired": "समाप्त",
    "starts {time}": "शुरू: {time}",
    "ends {time}": "समाप्त होगा: {time}",
    "ended {time}": "समाप्त हुआ: {time}",
    "Edit": "संपादित करें",
    "No links yet": "अभी कोई लिंक नहीं",
    "Paste a long URL above to create your first short link.":
        "अपना पहला छोटा लिंक बनाने के लिए ऊपर एक लंबा URL पेस्ट करें।",
    "Password protected": "पासवर्ड से सुरक्षित",
    # ---- link statistics ----
    "← All links": "← सभी लिंक",
    "Redirects to {url}": "{url} पर भेजता है",
    "{n} in the last 14 days": "पिछले 14 दिनों में {n}",
    "Edit link": "लिंक संपादित करें",
    "Clicks per day": "रोज़ के क्लिक",
    "Clicks per day for the last 14 days": "पिछले 14 दिनों के रोज़ के क्लिक",
    "QR code": "QR कोड",
    "QR code for {url}": "{url} के लिए QR कोड",
    "Download PNG": "PNG डाउनलोड करें",
    "Devices": "डिवाइस",
    "No clicks yet.": "अभी तक कोई क्लिक नहीं।",
    "Top referrers": "शीर्ष रेफ़रर",
    "Delete this link?": "यह लिंक हटाएँ?",
    "Delete link": "लिंक हटाएँ",
    "desktop": "डेस्कटॉप",
    "mobile": "मोबाइल",
    "tablet": "टैबलेट",
    "bot": "बॉट",
    "Direct": "सीधे",
    # ---- edit link ----
    "The short address stays the same. You can change where it goes, when it works, and who can open it.":
        "छोटा पता वही रहता है। आप बदल सकते हैं कि वह कहाँ जाए, कब काम करे और उसे कौन खोल सके।",
    "Schedule": "समय-सारणी",
    "Before the start time and after the end time, visitors see a message instead of being redirected. Times are in your local time. Leave a box empty for no limit.":
        "शुरू होने के समय से पहले और समाप्त होने के समय के बाद, आने वालों को रीडायरेक्ट होने की जगह एक संदेश दिखता है। समय आपके स्थानीय समय में हैं। कोई सीमा न चाहें तो खाना खाली छोड़ें।",
    "Right now this link is {state}.": "अभी यह लिंक {state} है।",
    "This link is password protected. Visitors must enter the password before they are sent to the destination.":
        "यह लिंक पासवर्ड से सुरक्षित है। गंतव्य पर भेजे जाने से पहले आने वालों को पासवर्ड डालना होगा।",
    "This link has no password, so anyone with the link can open it.":
        "इस लिंक पर कोई पासवर्ड नहीं है, इसलिए लिंक वाला कोई भी इसे खोल सकता है।",
    "Password options": "पासवर्ड विकल्प",
    "Keep the current password": "मौजूदा पासवर्ड रखें",
    "Nothing changes.": "कुछ नहीं बदलेगा।",
    "Change the password": "पासवर्ड बदलें",
    "Replace it with a new one.": "इसे नए पासवर्ड से बदलें।",
    "New password": "नया पासवर्ड",
    "4-72 characters": "4-72 अक्षर",
    "Remove the password": "पासवर्ड हटाएँ",
    "Anyone with the link can open it.": "लिंक वाला कोई भी इसे खोल सकता है।",
    "No password": "कोई पासवर्ड नहीं",
    "Set a password": "पासवर्ड सेट करें",
    "Visitors must enter it first.": "आने वालों को पहले इसे डालना होगा।",
    "Save changes": "बदलाव सहेजें",
    # ---- account settings ----
    "Settings sections": "सेटिंग्स के भाग",
    "Profile": "प्रोफ़ाइल",
    "Appearance": "रूप-रंग",
    "Delete account": "खाता हटाएँ",
    "Avatar": "अवतार",
    "Choose your avatar": "अपना अवतार चुनें",
    "Save avatar": "अवतार सहेजें",
    "Your short links look like {example}. If you change your username, your old links keep working, and your previous names stay reserved for you ({used} of {max} used).":
        "आपके छोटे लिंक {example} जैसे दिखते हैं। यूज़रनेम बदलने पर भी आपके पुराने लिंक चलते रहेंगे, और आपके पिछले नाम आपके लिए सुरक्षित रहेंगे ({max} में से {used} उपयोग हुए)।",
    "Previous names: {names}": "पिछले नाम: {names}",
    "New username": "नया यूज़रनेम",
    "3-20 characters: letters, numbers, underscore.": "3-20 अक्षर: अक्षर, अंक, अंडरस्कोर।",
    "Current password": "मौजूदा पासवर्ड",
    "Change username": "यूज़रनेम बदलें",
    "Current email: {email}": "मौजूदा ईमेल: {email}",
    "Changing email is not available on this server yet (email sending is not set up).":
        "इस सर्वर पर ईमेल बदलना अभी उपलब्ध नहीं है (ईमेल भेजना सेट नहीं है)।",
    "A code was sent to {email}.": "{email} पर एक कोड भेजा गया है।",
    "Enter the code": "कोड डालें",
    "Cancel email change": "ईमेल बदलना रद्द करें",
    "We email a 6-digit code to the new address. The change only happens once you enter it.":
        "हम नए पते पर 6 अंकों का कोड ईमेल करते हैं। आपके कोड डालने के बाद ही बदलाव होता है।",
    "New email address": "नया ईमेल पता",
    "Send verification code": "सत्यापन कोड भेजें",
    "Change password": "पासवर्ड बदलें",
    "8-72 characters.": "8-72 अक्षर।",
    "Choose how the site looks. \"System\" follows your device's setting.":
        "साइट कैसी दिखे, यह चुनें। \"सिस्टम\" आपके डिवाइस की सेटिंग का पालन करता है।",
    "Theme": "थीम",
    "System default": "सिस्टम डिफ़ॉल्ट",
    "Match my device": "मेरे डिवाइस के अनुसार",
    "Light": "लाइट",
    "Always light": "हमेशा लाइट",
    "Dark": "डार्क",
    "Always dark": "हमेशा डार्क",
    "Save appearance": "रूप-रंग सहेजें",
    "This permanently deletes your account, all your links, and their click history. Short links you already shared will stop working. This cannot be undone.":
        "यह आपका खाता, आपके सभी लिंक और उनका क्लिक इतिहास हमेशा के लिए हटा देता है। जो छोटे लिंक आप पहले साझा कर चुके हैं, वे काम करना बंद कर देंगे। इसे वापस नहीं किया जा सकता।",
    "Delete your account and all your links permanently?": "क्या अपना खाता और सभी लिंक हमेशा के लिए हटाएँ?",
    "Type your username to confirm": "पुष्टि के लिए अपना यूज़रनेम लिखें",
    "Delete my account": "मेरा खाता हटाएँ",
    # ---- date picker ----
    "Pick a date or type DD/MM/YYYY": "तारीख चुनें या DD/MM/YYYY लिखें",
    "Open calendar for {label}": "{label} के लिए कैलेंडर खोलें",
    "Previous month": "पिछला महीना",
    "Next month": "अगला महीना",
    "Month": "महीना",
    "Year": "वर्ष",
    "Days": "दिन",
    "Time": "समय",
    "Hour": "घंटा",
    "Minute": "मिनट",
    "Second": "सेकंड",
    "Clear": "साफ़ करें",
    "Today": "आज",
    "Done": "हो गया",
    "Choose start date and time": "शुरू होने की तारीख और समय चुनें",
    "Choose end date and time": "समाप्त होने की तारीख और समय चुनें",
    "Use a date like {example}, optionally with a time like 09:30 PM.":
        "{example} जैसी तारीख लिखें, चाहें तो 09:30 PM जैसा समय भी जोड़ें।",
    "e.g. {example}": "जैसे {example}",
    # ---- error pages ----
    "Page not found.": "पेज नहीं मिला।",
    "Not Found": "नहीं मिला",
    "Method Not Allowed": "यह तरीका अनुमत नहीं है",
    "This short link does not exist.": "यह छोटा लिंक मौजूद नहीं है।",
    "This short link has expired.": "यह छोटा लिंक समाप्त हो चुका है।",
    "This short link is not active yet. Please check back later.":
        "यह छोटा लिंक अभी चालू नहीं हुआ है। कृपया बाद में देखें।",
    "Link not found.": "लिंक नहीं मिला।",
    "No links to download.": "डाउनलोड करने के लिए कोई लिंक नहीं।",
    # ---- form checks ----
    "Username must be 3-20 characters: letters, numbers, underscore.":
        "यूज़रनेम 3-20 अक्षरों का होना चाहिए: अक्षर, अंक, अंडरस्कोर।",
    "That username is reserved.": "यह यूज़रनेम आरक्षित है।",
    "Enter a valid email address.": "सही ईमेल पता डालें।",
    "Password must be 8-72 characters.": "पासवर्ड 8-72 अक्षरों का होना चाहिए।",
    "Custom alias must be 3-32 characters: letters, numbers, - or _.":
        "कस्टम नाम 3-32 अक्षरों का होना चाहिए: अक्षर, अंक, - या _।",
    "Enter a URL.": "एक URL डालें।",
    "URL is too long (max 2048 characters).": "URL बहुत लंबा है (अधिकतम 2048 अक्षर)।",
    "URL cannot contain spaces.": "URL में खाली जगह (स्पेस) नहीं हो सकती।",
    "Only http and https links are allowed.": "केवल http और https लिंक की अनुमति है।",
    "That doesn't look like a valid URL.": "यह सही URL जैसा नहीं लग रहा।",
    "That URL has an invalid port.": "इस URL में पोर्ट सही नहीं है।",
    "That host is not allowed.": "इस होस्ट की अनुमति नहीं है।",
    "Private or local addresses are not allowed.": "निजी या लोकल पतों की अनुमति नहीं है।",
    "That date or time is not valid.": "यह तारीख या समय सही नहीं है।",
    "A link password must be 4-72 characters.": "लिंक का पासवर्ड 4-72 अक्षरों का होना चाहिए।",
    "The end time must be after the start time.":
        "समाप्ति का समय शुरू होने के समय के बाद का होना चाहिए।",
    "Unknown password option.": "पासवर्ड का विकल्प अज्ञात है।",
    "The end time must be in the future.": "समाप्ति का समय भविष्य में होना चाहिए।",
    # ---- messages after an action ----
    "You're creating links too quickly. Wait a minute.": "आप बहुत तेज़ी से लिंक बना रहे हैं। एक मिनट रुकें।",
    "You already have a link called '{slug}'.": "आपके पास '{slug}' नाम का लिंक पहले से है।",
    "Could not generate a unique code. Try again.": "अनोखा कोड नहीं बन सका। फिर कोशिश करें।",
    "That alias was just taken. Try another.": "यह नाम अभी-अभी किसी ने ले लिया। कोई दूसरा आज़माएँ।",
    "Created {url}": "बना दिया: {url}",
    "Select at least one link first.": "पहले कम से कम एक लिंक चुनें।",
    "Deleted {n} link(s).": "{n} लिंक हटाए गए।",
    "Link deleted.": "लिंक हटा दिया गया।",
    "Link updated.": "लिंक अपडेट हो गया।",
    "Too many attempts. Please wait a minute and try again.":
        "बहुत ज़्यादा कोशिशें हो गईं। कृपया एक मिनट रुककर फिर कोशिश करें।",
    "Wrong password. Try again.": "गलत पासवर्ड। फिर कोशिश करें।",
    "Too many attempts. Try again later.": "बहुत ज़्यादा कोशिशें हो गईं। बाद में फिर कोशिश करें।",
    "That username or email is already registered.": "यह यूज़रनेम या ईमेल पहले से पंजीकृत है।",
    "Account created. Welcome to Link Shortener!": "खाता बन गया। Link Shortener में आपका स्वागत है!",
    "Too many attempts. Wait a few minutes.": "बहुत ज़्यादा कोशिशें हो गईं। कुछ मिनट रुकें।",
    "Wrong username/email or password.": "यूज़रनेम/ईमेल या पासवर्ड गलत है।",
    "Too many attempts. Wait a few minutes and try again.":
        "बहुत ज़्यादा कोशिशें हो गईं। कुछ मिनट रुककर फिर कोशिश करें।",
    "That password is not correct.": "यह पासवर्ड सही नहीं है।",
    "Please pick one of the avatars shown.": "कृपया दिखाए गए अवतारों में से एक चुनें।",
    "Avatar updated.": "अवतार अपडेट हो गया।",
    "Unknown theme.": "थीम अज्ञात है।",
    "Appearance saved.": "रूप-रंग सहेज लिया गया।",
    "That is already your username.": "यह पहले से ही आपका यूज़रनेम है।",
    "That username is taken.": "यह यूज़रनेम पहले से लिया जा चुका है।",
    "You have already used {max} previous usernames, which is the limit.":
        "आप पिछले {max} यूज़रनेम इस्तेमाल कर चुके हैं, जो सीमा है।",
    "That username was just taken. Try another.": "यह यूज़रनेम अभी-अभी किसी ने ले लिया। कोई दूसरा आज़माएँ।",
    "Username changed to {name}. Your old links still work.":
        "यूज़रनेम बदलकर {name} हो गया। आपके पुराने लिंक अब भी चलते हैं।",
    "Password changed.": "पासवर्ड बदल गया।",
    "Changing email is not available on this server yet.": "इस सर्वर पर ईमेल बदलना अभी उपलब्ध नहीं है।",
    "That is already your email.": "यह पहले से ही आपका ईमेल है।",
    "That email is already used by another account.": "यह ईमेल पहले से किसी दूसरे खाते में इस्तेमाल हो रहा है।",
    "Please wait {seconds} seconds before asking for another code.":
        "दूसरा कोड माँगने से पहले कृपया {seconds} सेकंड रुकें।",
    "Too many codes requested. Try again in an hour.": "बहुत ज़्यादा कोड माँगे गए। एक घंटे बाद फिर कोशिश करें।",
    "We could not send the email. Please try again later.":
        "हम ईमेल नहीं भेज सके। कृपया बाद में फिर कोशिश करें।",
    "We sent a 6-digit code to {email}.": "हमने {email} पर 6 अंकों का कोड भेजा है।",
    "There is no email change in progress.": "कोई ईमेल बदलाव चल नहीं रहा है।",
    "That code has expired. Please start again.": "यह कोड समाप्त हो गया है। कृपया फिर से शुरू करें।",
    "Too many wrong codes. Please start again.": "बहुत ज़्यादा गलत कोड डाले गए। कृपया फिर से शुरू करें।",
    "That code is not correct.": "यह कोड सही नहीं है।",
    "That email was just taken by another account.": "यह ईमेल अभी-अभी किसी दूसरे खाते ने ले लिया।",
    "Email changed to {email}.": "ईमेल बदलकर {email} हो गया।",
    "We sent a new code.": "हमने नया कोड भेजा है।",
    "Email change cancelled.": "ईमेल बदलना रद्द कर दिया गया।",
    "Type your username exactly to confirm.": "पुष्टि के लिए अपना यूज़रनेम ठीक वैसा ही लिखें।",
    "Your account and all its links were deleted.": "आपका खाता और उसके सभी लिंक हटा दिए गए।",
    # ---- email ----
    "Your Link Shortener verification code": "आपका Link Shortener सत्यापन कोड",
    "Your Link Shortener verification code is {code}.\n\nIt expires in 10 minutes. If you did not ask to change your email, you can ignore this message.":
        "आपका Link Shortener सत्यापन कोड {code} है।\n\nयह 10 मिनट में समाप्त हो जाएगा। अगर आपने ईमेल बदलने के लिए नहीं कहा था, तो आप इस संदेश को अनदेखा कर सकते हैं।",
    # ---- email check at sign-up ----
    "Verify and create account": "सत्यापित करें और खाता बनाएँ",
    "Use a different email": "दूसरा ईमेल इस्तेमाल करें",
    "That sign-up has expired. Please start again.": "यह साइन-अप समाप्त हो गया है। कृपया फिर से शुरू करें।",
    "Too many codes were requested for this email. Try again in an hour.":
        "इस ईमेल के लिए बहुत ज़्यादा कोड माँगे गए। एक घंटे बाद फिर कोशिश करें।",
    "Sign-ups are very busy right now. Please try again later.":
        "अभी साइन-अप पर बहुत भीड़ है। कृपया बाद में फिर कोशिश करें।",
    "That username or email was just taken. Please start again.":
        "यह यूज़रनेम या ईमेल अभी-अभी किसी ने ले लिया। कृपया फिर से शुरू करें।",
    "Your Link Shortener sign-up code": "आपका Link Shortener साइन-अप कोड",
    "Your Link Shortener sign-up code is {code}.\n\nIt expires in 10 minutes. If you did not try to sign up, you can ignore this message.":
        "आपका Link Shortener साइन-अप कोड {code} है।\n\nयह 10 मिनट में समाप्त हो जाएगा। अगर आपने साइन अप करने की कोशिश नहीं की थी, तो आप इस संदेश को अनदेखा कर सकते हैं।",
    # ---- own profile photo ----
    "Change profile photo": "प्रोफ़ाइल फ़ोटो बदलें",
    "Profile photo": "प्रोफ़ाइल फ़ोटो",
    "Close": "बंद करें",
    "Upload from gallery": "गैलरी से अपलोड करें",
    "Take a photo": "फ़ोटो खींचें",
    "Capture": "फ़ोटो लें",
    "Remove photo": "फ़ोटो हटाएँ",
    "Zoom": "ज़ूम",
    "Rotate": "घुमाएँ",
    "Rotate left": "बाएँ घुमाएँ",
    "Rotate right": "दाएँ घुमाएँ",
    "Save photo": "फ़ोटो सहेजें",
    "Choose another photo": "दूसरी फ़ोटो चुनें",
    "Drag the photo to move it. Use the slider to zoom.": "फ़ोटो को खींचकर हिलाएँ। ज़ूम के लिए स्लाइडर इस्तेमाल करें।",
    "Profile photo updated.": "प्रोफ़ाइल फ़ोटो अपडेट हो गई।",
    "Profile photo removed.": "प्रोफ़ाइल फ़ोटो हटा दी गई।",
    "That file is not a valid photo. Please use a JPEG, PNG or WebP image.":
        "यह फ़ाइल सही फ़ोटो नहीं है। कृपया JPEG, PNG या WebP चित्र इस्तेमाल करें।",
    "The photo is too large. Please choose one under 2 MB.": "फ़ोटो बहुत बड़ी है। कृपया 2 MB से छोटी फ़ोटो चुनें।",
    "That photo's dimensions are too large. Please choose a smaller one.":
        "इस फ़ोटो का आकार बहुत बड़ा है। कृपया छोटी फ़ोटो चुनें।",
    "Too many photo uploads. Try again in an hour.": "बहुत ज़्यादा फ़ोटो अपलोड हो गईं। एक घंटे बाद फिर कोशिश करें।",
    "Please choose a photo first.": "कृपया पहले एक फ़ोटो चुनें।",
    "We could not open the camera. You can upload a photo instead.":
        "हम कैमरा नहीं खोल सके। आप इसकी जगह फ़ोटो अपलोड कर सकते हैं।",
    "Saving…": "सहेजा जा रहा है…",
    "The photo could not be saved. Please try again.": "फ़ोटो सहेजी नहीं जा सकी। कृपया फिर कोशिश करें।",
    "Choose a picture from your device": "अपने डिवाइस से कोई चित्र चुनें",
    "Use your camera": "अपना कैमरा इस्तेमाल करें",
    "Starting camera…": "कैमरा चालू हो रहा है…",
    "Reset": "रीसेट करें",
    "Preview": "पूर्वावलोकन",
    "Drop your photo here": "अपनी फ़ोटो यहाँ छोड़ें",
    "Zoom out": "ज़ूम घटाएँ",
    "Zoom in": "ज़ूम बढ़ाएँ",
    "Camera access is blocked. Click the camera icon in the address bar, choose Allow, then try again.":
        "कैमरा की अनुमति ब्लॉक है। एड्रेस बार में कैमरा आइकन पर क्लिक करें, Allow चुनें, फिर दोबारा कोशिश करें।",
    "No camera was found on this device.": "इस डिवाइस पर कोई कैमरा नहीं मिला।",
    "Your camera is being used by another app. Close it and try again.":
        "आपका कैमरा किसी दूसरे ऐप में इस्तेमाल हो रहा है। उसे बंद करें और फिर कोशिश करें।",
    # ---- avatar names ----
    "Cat": "बिल्ली", "Dog": "कुत्ता", "Fox": "लोमड़ी", "Panda": "पांडा", "Rabbit": "खरगोश",
    "Bear": "भालू", "Frog": "मेंढक", "Owl": "उल्लू", "Penguin": "पेंगुइन", "Pig": "सूअर",
    "Lion": "शेर", "Tiger": "बाघ", "Monkey": "बंदर", "Koala": "कोआला", "Mouse": "चूहा",
    "Chicken": "मुर्गी", "Duck": "बत्तख", "Elephant": "हाथी", "Wolf": "भेड़िया", "Raccoon": "रैकून",
    "Hamster": "हैम्स्टर", "Deer": "हिरण", "Giraffe": "जिराफ़", "Zebra": "ज़ेबरा", "Cow": "गाय",
    "Sheep": "भेड़", "Hedgehog": "हेजहॉग", "Turtle": "कछुआ", "Bat": "चमगादड़", "Octopus": "ऑक्टोपस",
    "Ladybug": "लेडीबग", "Bee": "मधुमक्खी", "Parrot": "तोता", "Crocodile": "मगरमच्छ", "Whale": "व्हेल",
    "Sloth": "स्लॉथ",
    # ---- selection toolbar: edit / compare stats ----
    "Select one link to edit it.":
        "संपादित करने के लिए एक लिंक चुनें।",
    "Select exactly one link to edit.":
        "संपादित करने के लिए ठीक एक लिंक चुनें।",
    "You can compare up to {n} links at a time.":
        "आप एक बार में अधिकतम {n} लिंक की तुलना कर सकते हैं।",
    "Compare links":
        "लिंक की तुलना करें",
    "Last 14 days":
        "पिछले 14 दिन",
    "All time":
        "अब तक के कुल",
    # ---- activity log and hourly view ----
    "Activity log":
        "गतिविधि लॉग",
    "Activity on {date}":
        "{date} की गतिविधि",
    "Busiest hour: {time}":
        "सबसे व्यस्त घंटा: {time}",
    "Click a day to see its clicks hour by hour.":
        "किसी दिन पर क्लिक करके उसके क्लिक घंटे-दर-घंटे देखें।",
    "Clicks per hour":
        "प्रति घंटा क्लिक",
    "Created":
        "बनाया गया",
    "Date":
        "तारीख़",
    "Expires":
        "समाप्त होगा",
    "Goes live":
        "चालू होगा",
    "Next day →":
        "अगला दिन →",
    "No clicks on this day.":
        "इस दिन कोई क्लिक नहीं हुआ।",
    "Partly active":
        "आंशिक रूप से चालू",
    "Showing the last {n} days.":
        "पिछले {n} दिन दिखाए जा रहे हैं।",
    "Went live":
        "चालू हुआ",
    "created {time}":
        "बनाया गया {time}",
    "{n} click":
        "{n} क्लिक",
    "{n} clicks":
        "{n} क्लिक",
    "← Previous day":
        "← पिछला दिन",
    # ---- link on/off switch ----
    "Inactive":
        "निष्क्रिय",
    "Deactivated":
        "बंद किया गया",
    "Activated":
        "चालू किया गया",
    "Deactivate link":
        "लिंक बंद करें",
    "Activate link":
        "लिंक चालू करें",
    "This link is on. Turn it off to stop it working right away. You can turn it back on at any time.":
        "यह लिंक चालू है। इसे तुरंत काम करना बंद करने के लिए बंद करें। आप इसे कभी भी फिर से चालू कर सकते हैं।",
    "This link is turned off. Visitors see a message instead of being sent to the destination.":
        "यह लिंक बंद है। आने वालों को गंतव्य पर भेजने के बजाय एक संदेश दिखता है।",
    "Link activated. It works again.":
        "लिंक चालू हो गया। यह फिर से काम करेगा।",
    "Link deactivated. Visitors can no longer open it.":
        "लिंक बंद हो गया। आने वाले अब इसे नहीं खोल सकते।",
    "This short link is turned off.":
        "यह छोटा लिंक बंद है।",
    # ---- landing page features ----
    "Custom aliases":
        "अपने नाम वाले लिंक",
    "Pick your own short name or get a random code. Change your username and your old links keep working.":
        "अपना छोटा नाम चुनें या अपने आप बना कोड पाएँ। यूज़रनेम बदलने पर भी आपके पुराने लिंक चलते रहते हैं।",
    "See when each link was created, when it was active or inactive, and its clicks day by day.":
        "देखें कि हर लिंक कब बना, कब चालू या निष्क्रिय रहा, और हर दिन उस पर कितने क्लिक आए।",
    "Hour by hour":
        "घंटे-दर-घंटे",
    "Open any day to see its clicks hour by hour, in your own time zone.":
        "किसी भी दिन को खोलकर अपने समय क्षेत्र में उसके क्लिक घंटे-दर-घंटे देखें।",
    "Select several links and compare their clicks in one graph.":
        "कई लिंक चुनें और उनके क्लिक एक ही ग्राफ़ में देखकर तुलना करें।",
    "Schedule links":
        "लिंक का समय तय करें",
    "Set a start and an end time, and links go live and expire on their own.":
        "शुरू और समाप्ति का समय तय करें, लिंक अपने आप चालू होंगे और समाप्त हो जाएँगे।",
    "On and off":
        "चालू और बंद",
    "Deactivate a link in one click and activate it again whenever you like.":
        "एक क्लिक में लिंक बंद करें और जब चाहें उसे फिर से चालू करें।",
    "Edit any time":
        "कभी भी बदलें",
    "Change the destination, schedule or password without changing the short address.":
        "छोटा पता बदले बिना गंतव्य, समय या पासवर्ड बदलें।",
    "Password protection":
        "पासवर्ड सुरक्षा",
    "Ask visitors for a password before they are sent on.":
        "आने वालों को आगे भेजने से पहले उनसे पासवर्ड माँगें।",
    "Your language":
        "आपकी भाषा",
    "Use it in English, हिन्दी or ગુજરાતી, with digits in your own script, in a light or dark theme.":
        "इसे अंग्रेज़ी, हिन्दी या ગુજરાતી में, अपनी लिपि के अंकों के साथ, हल्की या गहरी थीम में इस्तेमाल करें।",
    # ---- share pop-up ----
    "Share":
        "साझा करें",
    "Share link":
        "लिंक साझा करें",
    "Select one link to share it.":
        "साझा करने के लिए एक लिंक चुनें।",
    "Copy link":
        "लिंक कॉपी करें",
    "Download QR":
        "QR डाउनलोड करें",
    "Share via":
        "इनसे साझा करें",
    "Share via {app}":
        "{app} से साझा करें",
    "More":
        "और",
    "Check out this link":
        "यह लिंक देखें",
    "This link is not active right now, so visitors will see a message instead.":
        "यह लिंक अभी चालू नहीं है, इसलिए खोलने वालों को इसके बजाय एक संदेश दिखेगा।",
    "Copied!":
        "कॉपी हो गया!",
    "Could not copy automatically. Select the link and copy it.":
        "अपने आप कॉपी नहीं हो सका। लिंक चुनकर खुद कॉपी करें।",
    # ---- analytics wording ----
    "Analytics":
        "एनालिटिक्स",
    "Select one or more links to see their analytics. Pick several to compare them in one graph.":
        "एनालिटिक्स देखने के लिए एक या अधिक लिंक चुनें। एक ही ग्राफ़ में तुलना करने के लिए कई लिंक चुनें।",
    "← Back to link analytics":
        "← लिंक एनालिटिक्स पर वापस",
    # ---- chart types and hourly graph ----
    "Chart type":
        "ग्राफ़ का प्रकार",
    "Bar":
        "बार",
    "Line":
        "लाइन",
    "Area":
        "एरिया",
    "Clicks today, hour by hour":
        "आज के क्लिक, घंटे-दर-घंटे",
    "{n} click today":
        "आज {n} क्लिक",
    "{n} clicks today":
        "आज {n} क्लिक",
    "No clicks yet today.":
        "आज अभी तक कोई क्लिक नहीं हुआ।",
    # ---- audience (sources, devices, places, best time) ----
    "Audience":
        "दर्शक",
    "Time period":
        "समय अवधि",
    "Last {n} days":
        "पिछले {n} दिन",
    "Unique visitors":
        "यूनिक विज़िटर",
    "Returning visitors":
        "दोबारा आने वाले विज़िटर",
    "Each person is counted once, however many times they click.":
        "हर व्यक्ति को एक ही बार गिना जाता है, चाहे वह कितनी भी बार क्लिक करे।",
    "{n}% of visitors clicked more than once.":
        "{n}% विज़िटर ने एक से ज़्यादा बार क्लिक किया।",
    "Busiest time":
        "सबसे व्यस्त समय",
    "Visitors per day":
        "रोज़ के विज़िटर",
    "{n} unique visitors in the last 14 days":
        "पिछले 14 दिनों में {n} यूनिक विज़िटर",
    "Clicks recorded before visitor tracking are not counted as visitors.":
        "विज़िटर ट्रैकिंग से पहले दर्ज हुए क्लिक विज़िटर में नहीं गिने जाते।",
    "No clicks in this period yet.":
        "इस अवधि में अभी तक कोई क्लिक नहीं।",
    "Where clicks come from":
        "क्लिक कहाँ से आते हैं",
    "Sources":
        "स्रोत",
    "Tip: add {example} to the end of a short link you share to count it under that name.":
        "सुझाव: साझा किए जाने वाले छोटे लिंक के अंत में {example} जोड़ें, ताकि वह उसी नाम से गिना जाए।",
    "Browsers":
        "ब्राउज़र",
    "Operating systems":
        "ऑपरेटिंग सिस्टम",
    "Where visitors are":
        "विज़िटर कहाँ हैं",
    "Countries":
        "देश",
    "Cities":
        "शहर",
    "No location data yet. It is recorded for new clicks.":
        "अभी कोई स्थान डेटा नहीं है। यह नए क्लिक के लिए दर्ज होता है।",
    "{n} click has no location yet.":
        "{n} क्लिक का स्थान अभी उपलब्ध नहीं है।",
    "{n} clicks have no location yet.":
        "{n} क्लिक का स्थान अभी उपलब्ध नहीं है।",
    "Best time of day":
        "दिन का सबसे अच्छा समय",
    "Clicks by weekday and hour ({tz})":
        "सप्ताह के दिन और घंटे के अनुसार क्लिक ({tz})",
    "Fewer":
        "कम",
    "Other websites":
        "अन्य वेबसाइटें",
    "Unknown":
        "अज्ञात",
    "Other":
        "अन्य",
    "In-app browser":
        "ऐप का ब्राउज़र",
    # ---- click limit, tags, archive ----
    "A link can have up to 5 tags.":
        "एक लिंक पर ज़्यादा से ज़्यादा 5 टैग हो सकते हैं।",
    "A tag can be up to 24 characters, without symbols like # ? / & or quotes.":
        "टैग 24 अक्षरों तक का हो सकता है, और उसमें # ? / & या उद्धरण चिह्न जैसे प्रतीक नहीं होने चाहिए।",
    "Advanced":
        "उन्नत",
    "All":
        "सभी",
    "Archive":
        "आर्काइव",
    "Archive link":
        "लिंक आर्काइव करें",
    "Archived":
        "आर्काइव किए गए",
    "Archived links are hidden from your dashboard list but keep working and keep their stats.":
        "आर्काइव किए गए लिंक आपकी डैशबोर्ड सूची में नहीं दिखते, लेकिन काम करते रहते हैं और उनके आँकड़े बने रहते हैं।",
    "Archived links are hidden from your list but still work. Select links and press Archive to put them here.":
        "आर्काइव किए गए लिंक आपकी सूची में नहीं दिखते, लेकिन काम करते रहते हैं। लिंक चुनें और उन्हें यहाँ रखने के लिए आर्काइव दबाएँ।",
    "Archived {n} link(s). They are hidden from your list but still work.":
        "{n} लिंक आर्काइव किए गए। वे आपकी सूची में नहीं दिखेंगे, लेकिन काम करते रहेंगे।",
    "Bring the selected links back to your list.":
        "चुने हुए लिंक को वापस अपनी सूची में लाएँ।",
    "Click limit":
        "क्लिक सीमा",
    "Click limit reached":
        "क्लिक सीमा पूरी हुई",
    "Compare this tag":
        "इस टैग की तुलना करें",
    "Hide the selected links from this list. They keep working and keep their stats.":
        "चुने हुए लिंक को इस सूची से छिपाएँ। वे काम करते रहेंगे और उनके आँकड़े बने रहेंगे।",
    "Limit reached":
        "सीमा पूरी",
    "Link archived. It is hidden from your list but still works.":
        "लिंक आर्काइव हो गया। वह आपकी सूची में नहीं दिखेगा, लेकिन काम करता रहेगा।",
    "Link restored.":
        "लिंक वापस ला दिया गया।",
    "Maximum clicks":
        "अधिकतम क्लिक",
    "More options: schedule, password and advanced":
        "और विकल्प: समय-सारणी, पासवर्ड और उन्नत",
    "No archived links":
        "कोई आर्काइव किया हुआ लिंक नहीं",
    "No limit":
        "कोई सीमा नहीं",
    "No links have that tag.":
        "किसी भी लिंक पर वह टैग नहीं है।",
    "No links with this tag":
        "इस टैग वाला कोई लिंक नहीं",
    "Restore":
        "वापस लाएँ",
    "Restore link":
        "लिंक वापस लाएँ",
    "Restored {n} link(s).":
        "{n} लिंक वापस लाए गए।",
    "Separate tags with commas. Up to 5 per link.":
        "टैग को कॉमा से अलग करें। हर लिंक पर 5 तक।",
    "Showing the {n} most-clicked links of this tag.":
        "इस टैग के सबसे ज़्यादा क्लिक वाले {n} लिंक दिखाए जा रहे हैं।",
    "Tags":
        "टैग",
    "Tags group your links. You can filter the dashboard by a tag and compare all its links in one graph.":
        "टैग आपके लिंक को समूह में रखते हैं। आप डैशबोर्ड को किसी टैग से फ़िल्टर कर सकते हैं और उसके सभी लिंक की एक ग्राफ़ में तुलना कर सकते हैं।",
    "The click limit must be a whole number from 1 to 1,000,000.":
        "क्लिक सीमा 1 से 1,000,000 के बीच की पूरी संख्या होनी चाहिए।",
    "The link stops working after this many clicks. Good for one-time links.":
        "इतने क्लिक के बाद लिंक काम करना बंद कर देता है। एक बार वाले लिंक के लिए अच्छा।",
    "The link stops working after this many clicks. Good for one-time links. Leave the box empty for no limit.":
        "इतने क्लिक के बाद लिंक काम करना बंद कर देता है। एक बार वाले लिंक के लिए अच्छा। कोई सीमा न चाहिए तो बॉक्स खाली छोड़ें।",
    "This feature is part of a paid plan.":
        "यह सुविधा सशुल्क प्लान का हिस्सा है।",
    "This link is archived.":
        "यह लिंक आर्काइव किया हुआ है।",
    "This short link has reached its click limit.":
        "इस छोटे लिंक की क्लिक सीमा पूरी हो चुकी है।",
    "Which links to show":
        "कौन से लिंक दिखाएँ",
    "You can have up to 50 tags in total.":
        "आपके कुल मिलाकर 50 टैग तक हो सकते हैं।",
    "e.g. work, school":
        "जैसे: काम, स्कूल",
    "{n} click used so far.":
        "अब तक {n} क्लिक इस्तेमाल हुआ।",
    "{n} clicks used so far.":
        "अब तक {n} क्लिक इस्तेमाल हुए।",
    "{used} of {limit} clicks used":
        "{limit} में से {used} क्लिक इस्तेमाल हुए",
    # ---- link check ----
    "This web address is on a list of unsafe sites, so it can't be shortened.":
        "यह वेब पता असुरक्षित साइटों की सूची में है, इसलिए इसे छोटा नहीं किया जा सकता।",
    "Heads up: that address did not answer when we checked it. The link was saved anyway, but please make sure the address is correct.":
        "ध्यान दें: जाँच करते समय उस पते ने जवाब नहीं दिया। लिंक फिर भी सहेज लिया गया है, लेकिन कृपया जाँच लें कि पता सही है।",
    # ---- destination history ----
    "Destination changed":
        "गंतव्य बदला गया",
    "Every change to the destination is written in the activity log.":
        "गंतव्य में हर बदलाव गतिविधि लॉग में दर्ज होता है।",
    # ---- csv import ----
    "Import links":
        "लिंक आयात करें",
    "Add many links at once from a CSV file, for example one made with Export CSV.":
        "CSV फ़ाइल से एक साथ कई लिंक जोड़ें, जैसे CSV एक्सपोर्ट से बनी फ़ाइल।",
    "Imported {n} link.":
        "{n} लिंक आयात हुआ।",
    "Imported {n} links.":
        "{n} लिंक आयात हुए।",
    "{n} row was skipped.":
        "{n} पंक्ति छोड़ दी गई।",
    "{n} rows were skipped.":
        "{n} पंक्तियाँ छोड़ दी गईं।",
    "Row":
        "पंक्ति",
    "Address":
        "पता",
    "Why it was skipped":
        "क्यों छोड़ी गई",
    "Only the first 20 skipped rows are shown.":
        "छोड़ी गई पंक्तियों में से केवल पहली 20 दिखाई गई हैं।",
    "Go to my links":
        "मेरे लिंक पर जाएँ",
    "Choose a file":
        "फ़ाइल चुनें",
    "CSV file":
        "CSV फ़ाइल",
    "Import":
        "आयात करें",
    "Up to 200 links and 500 KB in one file.":
        "एक फ़ाइल में 200 लिंक और 500 KB तक।",
    "What the file needs":
        "फ़ाइल में क्या होना चाहिए",
    "The first row holds the column names. Only original_url is required.":
        "पहली पंक्ति में कॉलम के नाम होते हैं। केवल original_url ज़रूरी है।",
    "The long web address. Required.":
        "लंबा वेब पता। ज़रूरी।",
    "Your own short name. Leave it empty to get a random one.":
        "आपका अपना छोटा नाम। खाली छोड़ेंगे तो अपने आप एक नाम मिलेगा।",
    "A date like 2027-12-31, or a date and time like 2027-12-31 18:00.":
        "2027-12-31 जैसी तारीख़, या 2027-12-31 18:00 जैसी तारीख़ और समय।",
    "A number of clicks. Use 1 for a one-time link.":
        "क्लिक की संख्या। एक बार वाले लिंक के लिए 1 लिखें।",
    "Tag names separated by commas.":
        "टैग के नाम, कॉमा से अलग किए हुए।",
    "Write no to import the link switched off.":
        "लिंक को बंद करके आयात करने के लिए no लिखें।",
    "Passwords are never imported. Each address is checked against the unsafe-sites list, but not opened to see whether it answers.":
        "पासवर्ड कभी आयात नहीं होते। हर पते को असुरक्षित साइटों की सूची से मिलाया जाता है, लेकिन यह देखने के लिए नहीं खोला जाता कि वह जवाब देता है या नहीं।",
    "Download a sample file":
        "नमूना फ़ाइल डाउनलोड करें",
    "Import many links from a CSV file":
        "CSV फ़ाइल से कई लिंक आयात करें",
    "That file is too big. The most is 500 KB.":
        "वह फ़ाइल बहुत बड़ी है। अधिकतम 500 KB की अनुमति है।",
    "That is not a text (UTF-8) CSV file.":
        "यह टेक्स्ट (UTF-8) CSV फ़ाइल नहीं है।",
    "The first row must hold the column names, including original_url.":
        "पहली पंक्ति में कॉलम के नाम होने चाहिए, जिनमें original_url भी हो।",
    "The file has no links in it.":
        "फ़ाइल में कोई लिंक नहीं है।",
    "A file can have up to 200 links. Split it into smaller files.":
        "एक फ़ाइल में 200 लिंक तक हो सकते हैं। उसे छोटी फ़ाइलों में बाँटें।",
    "You're importing too quickly. Wait a minute.":
        "आप बहुत जल्दी आयात कर रहे हैं। एक मिनट रुकें।",
    "Choose a CSV file first.":
        "पहले एक CSV फ़ाइल चुनें।",
    # ---- guide page ----
    "Guide":
        "गाइड",
    "Everything this site can do, with simple steps for each feature.":
        "यह साइट जो कुछ भी कर सकती है, हर सुविधा के सरल चरणों के साथ।",
    "On this page":
        "इस पेज पर",
    "Create a short link":
        "छोटा लिंक बनाएँ",
    "Turn a long web address into a short one that is easy to share.":
        "लंबे वेब पते को छोटे पते में बदलें, जिसे साझा करना आसान हो।",
    "Paste the long address into the Long URL box on your dashboard.":
        "अपने डैशबोर्ड पर \"लंबा URL\" वाले बॉक्स में लंबा पता चिपकाएँ।",
    "If you like, type your own short name in Custom alias. Otherwise a random one is made.":
        "चाहें तो \"कस्टम नाम\" में अपना छोटा नाम लिखें। नहीं तो अपने आप एक नाम बन जाता है।",
    "Press Shorten, then copy or share your new link.":
        "\"छोटा करें\" दबाएँ, फिर अपना नया लिंक कॉपी या साझा करें।",
    "Schedule a link":
        "लिंक की समय-सारणी बनाएँ",
    "Make a link work only between two moments.":
        "लिंक को केवल दो समयों के बीच काम करने दें।",
    "Open More options when creating a link, or press Edit on an existing one.":
        "लिंक बनाते समय \"और विकल्प\" खोलें, या पहले से बने लिंक पर \"संपादित करें\" दबाएँ।",
    "Pick a start time, an end time, or both.":
        "शुरू होने का समय, समाप्त होने का समय, या दोनों चुनें।",
    "Before the start and after the end, visitors see a message instead of being sent on.":
        "शुरू होने से पहले और समाप्त होने के बाद, आने वालों को आगे भेजने की जगह एक संदेश दिखता है।",
    "Password-protected links":
        "पासवर्ड वाले लिंक",
    "Only people who know the password can open the link.":
        "केवल पासवर्ड जानने वाले लोग ही लिंक खोल सकते हैं।",
    "Open More options and type a password, or choose Set a password on the Edit page.":
        "\"और विकल्प\" खोलकर पासवर्ड लिखें, या संपादन पेज पर \"पासवर्ड सेट करें\" चुनें।",
    "Share the link, and tell people the password separately.":
        "लिंक साझा करें, और पासवर्ड लोगों को अलग से बताएँ।",
    "On the Edit page, choose No password to remove it.":
        "उसे हटाने के लिए संपादन पेज पर \"कोई पासवर्ड नहीं\" चुनें।",
    "A link that stops working after a set number of clicks, ideal for one-time links.":
        "ऐसा लिंक जो तय संख्या में क्लिक के बाद काम करना बंद कर देता है, एक बार वाले लिंक के लिए बढ़िया।",
    "Open More options, then Advanced, and type a number in Click limit.":
        "\"और विकल्प\" खोलें, फिर \"उन्नत\" में \"क्लिक सीमा\" में एक संख्या लिखें।",
    "Every real visit uses one click. Link previews from chat apps do not.":
        "हर असली विज़िट एक क्लिक इस्तेमाल करती है। चैट ऐप के लिंक प्रीव्यू नहीं करते।",
    "To open the link again, raise the limit on the Edit page.":
        "लिंक को फिर से खोलने के लिए संपादन पेज पर सीमा बढ़ाएँ।",
    "Group your links with labels such as work or school.":
        "अपने लिंक को काम या स्कूल जैसे लेबल से समूह में रखें।",
    "Type tags separated by commas when you create or edit a link.":
        "लिंक बनाते या संपादित करते समय टैग को कॉमा से अलग करके लिखें।",
    "Click a tag above your list to see only the links that have it.":
        "सूची के ऊपर किसी टैग पर क्लिक करें, तो केवल वही लिंक दिखेंगे जिन पर वह टैग है।",
    "Press Compare this tag to see all its links in one graph.":
        "उसके सभी लिंक एक ग्राफ़ में देखने के लिए \"इस टैग की तुलना करें\" दबाएँ।",
    "Tidy your list without losing anything.":
        "कुछ खोए बिना अपनी सूची साफ़ रखें।",
    "Tick one or more links and press Archive.":
        "एक या ज़्यादा लिंक चुनें और \"आर्काइव\" दबाएँ।",
    "Open the Archived tab to see them, and press Restore to bring them back.":
        "उन्हें देखने के लिए \"आर्काइव किए गए\" टैब खोलें, और वापस लाने के लिए \"वापस लाएँ\" दबाएँ।",
    "Archived links keep working and keep their stats. Use Deactivate link to stop one.":
        "आर्काइव किए गए लिंक काम करते रहते हैं और उनके आँकड़े बने रहते हैं। किसी को रोकने के लिए \"लिंक बंद करें\" का उपयोग करें।",
    "Edit a link":
        "लिंक संपादित करें",
    "Change a link without changing its short address.":
        "लिंक का छोटा पता बदले बिना उसमें बदलाव करें।",
    "Tick a link and press Edit.":
        "एक लिंक चुनें और \"संपादित करें\" दबाएँ।",
    "Change the destination, schedule, click limit, tags or password, then save.":
        "गंतव्य, समय-सारणी, क्लिक सीमा, टैग या पासवर्ड बदलें, फिर सहेजें।",
    "Every change of destination is written in the activity log, with the old and new address.":
        "गंतव्य का हर बदलाव गतिविधि लॉग में पुराने और नए पते के साथ दर्ज होता है।",
    "See who clicks your links.":
        "देखें कि आपके लिंक पर कौन क्लिक करता है।",
    "Tick a link and press Analytics.":
        "एक लिंक चुनें और \"एनालिटिक्स\" दबाएँ।",
    "Read the graphs of clicks by hour and by day. Click a day to see its hours.":
        "घंटे और दिन के अनुसार क्लिक के ग्राफ़ देखें। किसी दिन पर क्लिक करके उसके घंटे देखें।",
    "Further down, the Audience section shows where visitors come from, what they use, where they are, and the best time of day.":
        "नीचे \"दर्शक\" भाग दिखाता है कि विज़िटर कहाँ से आते हैं, क्या इस्तेमाल करते हैं, कहाँ हैं, और दिन का सबसे अच्छा समय कौन-सा है।",
    "To compare links, tick several and press Analytics.":
        "लिंक की तुलना के लिए कई लिंक चुनें और \"एनालिटिक्स\" दबाएँ।",
    "Share and QR codes":
        "साझा करना और QR कोड",
    "Send a link in a tap, or print a QR code.":
        "एक टैप में लिंक भेजें, या QR कोड प्रिंट करें।",
    "Tick a link and press Share to copy it or send it with an app.":
        "एक लिंक चुनें और उसे कॉपी करने या किसी ऐप से भेजने के लिए \"साझा करें\" दबाएँ।",
    "In the Share window, press Download QR to save its QR code.":
        "साझा करने की विंडो में उसका QR कोड सहेजने के लिए \"QR डाउनलोड करें\" दबाएँ।",
    "Download QR codes on the dashboard saves one for every link you ticked.":
        "डैशबोर्ड पर \"QR कोड डाउनलोड करें\" आपके चुने हर लिंक का एक QR कोड सहेजता है।",
    "Import and export":
        "आयात और एक्सपोर्ट",
    "Move your links in and out with a spreadsheet file.":
        "स्प्रेडशीट फ़ाइल से अपने लिंक अंदर और बाहर ले जाएँ।",
    "Press Export CSV to download all your links.":
        "अपने सभी लिंक डाउनलोड करने के लिए \"CSV एक्सपोर्ट करें\" दबाएँ।",
    "Press Import many links from a CSV file and choose a file with an original_url column.":
        "\"CSV फ़ाइल से कई लिंक आयात करें\" दबाएँ और original_url कॉलम वाली फ़ाइल चुनें।",
    "Rows that cannot be imported are skipped and listed with the reason.":
        "जो पंक्तियाँ आयात नहीं हो सकतीं, उन्हें कारण सहित छोड़कर सूची में दिखाया जाता है।",
    "Safety check":
        "सुरक्षा जाँच",
    "We look at an address before turning it into a link.":
        "पते को लिंक बनाने से पहले हम उसकी जाँच करते हैं।",
    "Addresses on a list of unsafe sites are refused.":
        "असुरक्षित साइटों की सूची वाले पते स्वीकार नहीं किए जाते।",
    "If an address does not answer, you get a warning, but the link is still saved.":
        "अगर कोई पता जवाब नहीं देता, तो आपको चेतावनी मिलती है, लेकिन लिंक फिर भी सहेज लिया जाता है।",
    "Links to private or local addresses are never allowed.":
        "निजी या स्थानीय पतों के लिंक की कभी अनुमति नहीं होती।",
    # ---- preview page, tracking tags, QR style ----
    "Show a preview page before redirecting":
        "रीडायरेक्ट से पहले पूर्वावलोकन पेज दिखाएँ",
    "Visitors see where they are going and press Continue. A click is counted only then.":
        "आने वाले देखते हैं कि वे कहाँ जा रहे हैं और \"आगे बढ़ें\" दबाते हैं। क्लिक तभी गिना जाता है।",
    "Message for visitors":
        "आने वालों के लिए संदेश",
    "A message for visitors (optional)":
        "आने वालों के लिए एक संदेश (वैकल्पिक)",
    "Campaign tracking (UTM)":
        "कैंपेन ट्रैकिंग (UTM)",
    "These tags are added to the end of the destination address, so analytics tools can tell where your visitors came from.":
        "ये टैग गंतव्य पते के अंत में जोड़े जाते हैं, ताकि एनालिटिक्स टूल बता सकें कि आपके विज़िटर कहाँ से आए।",
    "Source":
        "स्रोत",
    "Medium":
        "माध्यम",
    "Campaign":
        "कैंपेन",
    "Term":
        "शब्द",
    "Content":
        "सामग्री",
    "Visitors will land on:":
        "विज़िटर यहाँ पहुँचेंगे:",
    "Visitors see a preview page first":
        "आने वालों को पहले पूर्वावलोकन पेज दिखता है",
    "Preview page":
        "पूर्वावलोकन पेज",
    "Show visitors where they are going and let them press Continue. A click is counted only then.":
        "आने वालों को दिखाएँ कि वे कहाँ जा रहे हैं और उन्हें \"आगे बढ़ें\" दबाने दें। क्लिक तभी गिना जाता है।",
    "Choose colours and put a small logo in the middle. Keep the code dark on a light background so phones can scan it.":
        "रंग चुनें और बीच में एक छोटा लोगो लगाएँ। कोड को हल्की पृष्ठभूमि पर गहरा रखें ताकि फ़ोन उसे स्कैन कर सकें।",
    "Code colour":
        "कोड का रंग",
    "Background colour":
        "पृष्ठभूमि का रंग",
    "Logo in the centre":
        "बीच में लोगो",
    "Remove the logo":
        "लोगो हटाएँ",
    "PNG, JPG or WebP, up to 1 MB. It is shrunk and placed in the middle.":
        "PNG, JPG या WebP, अधिकतम 1 MB। उसे छोटा करके बीच में लगाया जाता है।",
    "Save QR style":
        "QR शैली सहेजें",
    "Back to the plain code":
        "सादे कोड पर वापस जाएँ",
    "Download SVG":
        "SVG डाउनलोड करें",
    "Change style":
        "शैली बदलें",
    "Download QR as SVG":
        "QR को SVG में डाउनलोड करें",
    "You're going to {host}":
        "आप {host} पर जा रहे हैं",
    "Before you continue":
        "आगे बढ़ने से पहले",
    "You will be taken to this address:":
        "आपको इस पते पर ले जाया जाएगा:",
    "A message from the link's owner":
        "लिंक के मालिक का संदेश",
    "Written by the link's owner, not by this site.":
        "यह संदेश लिंक के मालिक ने लिखा है, इस साइट ने नहीं।",
    "Go back":
        "वापस जाएँ",
    "Only continue if you trust this address.":
        "केवल तभी आगे बढ़ें जब आप इस पते पर भरोसा करते हों।",
    "Each tracking tag can be up to 100 characters.":
        "हर ट्रैकिंग टैग 100 अक्षरों तक का हो सकता है।",
    "The message can be up to 200 characters.":
        "संदेश 200 अक्षरों तक का हो सकता है।",
    "Pick colours as #RRGGBB values, for example #1a2b3c.":
        "रंग #RRGGBB रूप में चुनें, जैसे #1a2b3c।",
    "The colours need more contrast so phones can scan the code. Use a darker code colour on a lighter background.":
        "फ़ोन से स्कैन हो सके, इसके लिए रंगों में और अंतर चाहिए। हल्की पृष्ठभूमि पर गहरे रंग का कोड रखें।",
    "The logo must be a PNG, JPG or WebP picture up to 1 MB.":
        "लोगो PNG, JPG या WebP तस्वीर होनी चाहिए, अधिकतम 1 MB।",
    "The QR code is back to the plain style.":
        "QR कोड सादी शैली में लौट आया।",
    "QR code style saved.":
        "QR कोड की शैली सहेज ली गई।",
    # ---- guide: preview, tracking tags, QR ----
    "Show visitors where they are going before they are sent on.":
        "आने वालों को आगे भेजने से पहले दिखाएँ कि वे कहाँ जा रहे हैं।",
    "Open More options, then Advanced, and tick Show a preview page before redirecting.":
        "\"और विकल्प\" खोलें, फिर \"उन्नत\" में \"रीडायरेक्ट से पहले पूर्वावलोकन पेज दिखाएँ\" पर निशान लगाएँ।",
    "Add a short message for visitors if you like. It is shown as written by you.":
        "चाहें तो आने वालों के लिए एक छोटा संदेश जोड़ें। वह आपके लिखे अनुसार दिखता है।",
    "Visitors press Continue to go on. A click is counted only then.":
        "आने वाले आगे जाने के लिए \"आगे बढ़ें\" दबाते हैं। क्लिक तभी गिना जाता है।",
    "Add tracking tags so your analytics tools know where visitors came from.":
        "ट्रैकिंग टैग जोड़ें ताकि आपके एनालिटिक्स टूल जान सकें कि विज़िटर कहाँ से आए।",
    "Open More options, then Advanced, and fill in Source, Medium or Campaign.":
        "\"और विकल्प\" खोलें, फिर \"उन्नत\" में \"स्रोत\", \"माध्यम\" या \"कैंपेन\" भरें।",
    "On the Edit page you can also fill in Term and Content.":
        "संपादन पेज पर आप \"शब्द\" और \"सामग्री\" भी भर सकते हैं।",
    "The tags are added to the destination address. You can check the result under Visitors will land on.":
        "टैग गंतव्य पते में जोड़ दिए जाते हैं। नतीजा आप \"विज़िटर यहाँ पहुँचेंगे:\" के नीचे देख सकते हैं।",
    "On the Edit page, open QR code to choose colours and a logo, and download the code as PNG or SVG.":
        "संपादन पेज पर \"QR कोड\" में रंग और लोगो चुनें, और कोड को PNG या SVG में डाउनलोड करें।",
    # ---- colour schemes ----
    "Colour scheme":
        "रंग योजना",
    "Default":
        "डिफ़ॉल्ट",
    "Classic":
        "क्लासिक",
    "Neon":
        "नियॉन",
    "The original blues":
        "मूल नीले रंग",
    "Soft blue and violet":
        "हल्का नीला और बैंगनी",
    "Glowing blue and purple":
        "चमकदार नीला और बैंगनी",
    "Unknown colour scheme.":
        "अज्ञात रंग योजना।",
    # ---- mode switch ----
    "Colour mode":
        "रंग मोड",
}
