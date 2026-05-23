"""
profile_questions.py — Pre-interview onboarding questions.

The bot asks these questions BEFORE the actual interview, in a warm,
conversational tone, in the candidate's chosen language. Translations are
hand-prepared (not LLM-generated at runtime) so that:

  - candidates from villages and small towns hear natural, simple phrasing
    in their own dialect
  - every candidate is asked the same core questions → consistent JSON
    profile for ATS / HR pipelines
  - we don't pay for translation tokens per session

Each question is one short, single-topic ask — no compound questions —
because they're delivered as speech and complex sentences are hard to
parse aurally.

Supported languages: en, hi, bn, te, pa, gu (must match LANGUAGES in
question_bank.py).

Some prompts use a `{role}` placeholder — streamlit_app substitutes the
candidate's applied role (e.g. "Housekeeping") before TTS.
"""


# Friendly intro played once before the first profile question.
# {name} is the candidate's name from the setup form.
PROFILE_INTRO = {
    "en": "Hello {name}, welcome! Before we begin the interview, I would like to know a little about you. Please answer at your own pace — there are no right or wrong answers. Take your time.",
    "hi": "नमस्ते {name}, स्वागत है! इंटरव्यू शुरू करने से पहले, मैं आपके बारे में थोड़ा जानना चाहता हूँ। आराम से जवाब दीजिए — कोई सही या गलत जवाब नहीं है। अपना समय लीजिए।",
    "bn": "নমস্কার {name}, স্বাগতম! ইন্টারভিউ শুরু করার আগে, আমি আপনার সম্পর্কে একটু জানতে চাই। নিজের গতিতে উত্তর দিন — কোনো সঠিক বা ভুল উত্তর নেই। সময় নিন।",
    "te": "నమస్కారం {name}, స్వాగతం! ఇంటర్వ్యూ ప్రారంభించే ముందు, మీ గురించి కొంచెం తెలుసుకోవాలనుకుంటున్నాను. ప్రశాంతంగా సమాధానం ఇవ్వండి — సరైన లేదా తప్పు సమాధానాలు లేవు. మీ సమయం తీసుకోండి.",
    "pa": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ {name}, ਜੀ ਆਇਆਂ ਨੂੰ! ਇੰਟਰਵਿਊ ਸ਼ੁਰੂ ਕਰਨ ਤੋਂ ਪਹਿਲਾਂ, ਮੈਂ ਤੁਹਾਡੇ ਬਾਰੇ ਥੋੜ੍ਹਾ ਜਾਣਨਾ ਚਾਹੁੰਦਾ ਹਾਂ। ਆਰਾਮ ਨਾਲ ਜਵਾਬ ਦਿਓ — ਕੋਈ ਸਹੀ ਜਾਂ ਗਲਤ ਜਵਾਬ ਨਹੀਂ ਹੈ। ਆਪਣਾ ਸਮਾਂ ਲਓ।",
    "gu": "નમસ્તે {name}, સ્વાગત છે! ઇન્ટરવ્યૂ શરૂ કરતા પહેલા, હું તમારા વિશે થોડું જાણવા માગું છું. શાંતિથી જવાબ આપો — કોઈ સાચો કે ખોટો જવાબ નથી. તમારો સમય લો.",
}


# Friendly close after all profile questions are answered, before interview.
PROFILE_OUTRO = {
    "en": "Thank you for sharing all that with me. Now let us begin your interview.",
    "hi": "इतनी जानकारी देने के लिए धन्यवाद। अब हम आपका इंटरव्यू शुरू करते हैं।",
    "bn": "এতকিছু জানানোর জন্য ধন্যবাদ। এখন আমরা আপনার ইন্টারভিউ শুরু করি।",
    "te": "ఇంత సమాచారం పంచుకున్నందుకు ధన్యవాదాలు. ఇప్పుడు మీ ఇంటర్వ్యూ ప్రారంభిద్దాం.",
    "pa": "ਇਹ ਸਭ ਦੱਸਣ ਲਈ ਤੁਹਾਡਾ ਧੰਨਵਾਦ। ਹੁਣ ਅਸੀਂ ਤੁਹਾਡਾ ਇੰਟਰਵਿਊ ਸ਼ੁਰੂ ਕਰਦੇ ਹਾਂ।",
    "gu": "આટલું બધું જણાવવા બદલ આભાર. હવે અમે તમારો ઇન્ટરવ્યૂ શરૂ કરીએ.",
}


# 10 onboarding questions. Each has:
#   - field: profile-builder field key (must match _QUESTION_FIELD_ORDER
#            in utils/profile_builder.py)
#   - prompts: per-language text the bot speaks; may contain `{role}`
#              which streamlit_app substitutes before TTS.
#
# Order matters — easy/comfortable topics first (name, age), more
# detailed/sensitive ones (salary) later. Family question is intentionally
# light and respectful.
PROFILE_QUESTIONS = [
    {
        "field": "contact_info",
        "prompts": {
            "en": "Could you tell me your full name, mobile number and email ID?",
            "hi": "क्या आप मुझे अपना पूरा नाम, मोबाइल नंबर और ईमेल आईडी बता सकते हैं?",
            "bn": "আপনি কি আমাকে আপনার পুরো নাম, মোবাইল নম্বর এবং ইমেইল আইডি বলতে পারবেন?",
            "te": "మీ పూర్తి పేరు, మొబైల్ నంబర్ మరియు ఇమెయిల్ ఐడీ చెప్పగలరా?",
            "pa": "ਕੀ ਤੁਸੀਂ ਮੈਨੂੰ ਆਪਣਾ ਪੂਰਾ ਨਾਮ, ਮੋਬਾਈਲ ਨੰਬਰ ਅਤੇ ਈਮੇਲ ਆਈਡੀ ਦੱਸ ਸਕਦੇ ਹੋ?",
            "gu": "શું તમે મને તમારું પૂરું નામ, મોબાઇલ નંબર અને ઇમેઇલ આઇડી જણાવી શકો છો?",
        },
    },
    {
        "field": "location_and_age",
        "prompts": {
            "en": "How old are you, and which city or town are you currently based in?",
            "hi": "आपकी उम्र क्या है, और आप अभी किस शहर या कस्बे में रहते हैं?",
            "bn": "আপনার বয়স কত, এবং আপনি বর্তমানে কোন শহর বা গ্রামে থাকেন?",
            "te": "మీ వయస్సు ఎంత, మరియు మీరు ప్రస్తుతం ఏ నగరంలో లేదా పట్టణంలో ఉన్నారు?",
            "pa": "ਤੁਹਾਡੀ ਉਮਰ ਕੀ ਹੈ, ਅਤੇ ਤੁਸੀਂ ਇਸ ਵੇਲੇ ਕਿਹੜੇ ਸ਼ਹਿਰ ਜਾਂ ਕਸਬੇ ਵਿੱਚ ਰਹਿੰਦੇ ਹੋ?",
            "gu": "તમારી ઉંમર કેટલી છે, અને તમે હાલમાં કયા શહેર કે ગામમાં રહો છો?",
        },
    },
    {
        "field": "languages",
        "prompts": {
            "en": "Which languages can you speak comfortably?",
            "hi": "आप कौन-कौन सी भाषाएँ आराम से बोल सकते हैं?",
            "bn": "আপনি কোন কোন ভাষা স্বাচ্ছন্দ্যে বলতে পারেন?",
            "te": "మీరు ఏ భాషలు సునాయాసంగా మాట్లాడగలరు?",
            "pa": "ਤੁਸੀਂ ਕਿਹੜੀਆਂ-ਕਿਹੜੀਆਂ ਭਾਸ਼ਾਵਾਂ ਆਰਾਮ ਨਾਲ ਬੋਲ ਸਕਦੇ ਹੋ?",
            "gu": "તમે કઈ-કઈ ભાષાઓ સરળતાથી બોલી શકો છો?",
        },
    },
    {
        "field": "family",
        "prompts": {
            "en": "Tell me a little about your family — are you married, and do you have anyone who depends on you?",
            "hi": "अपने परिवार के बारे में थोड़ा बताइए — क्या आप शादीशुदा हैं, और क्या कोई आप पर निर्भर है?",
            "bn": "আপনার পরিবার সম্পর্কে একটু বলুন — আপনি কি বিবাহিত, এবং কেউ কি আপনার উপর নির্ভরশীল?",
            "te": "మీ కుటుంబం గురించి కొంచెం చెప్పండి — మీరు వివాహితులా, మరియు మీపై ఎవరైనా ఆధారపడి ఉన్నారా?",
            "pa": "ਆਪਣੇ ਪਰਿਵਾਰ ਬਾਰੇ ਥੋੜ੍ਹਾ ਦੱਸੋ — ਕੀ ਤੁਸੀਂ ਵਿਆਹੇ ਹੋਏ ਹੋ, ਅਤੇ ਕੀ ਕੋਈ ਤੁਹਾਡੇ ਉੱਤੇ ਨਿਰਭਰ ਹੈ?",
            "gu": "તમારા પરિવાર વિશે થોડું જણાવો — શું તમે પરિણીત છો, અને શું કોઈ તમારા પર નિર્ભર છે?",
        },
    },
    {
        "field": "experience_years",
        "prompts": {
            "en": "How many years of experience do you have in {role}-related work?",
            "hi": "आपको {role} से जुड़े काम का कितने साल का अनुभव है?",
            "bn": "{role} সংক্রান্ত কাজে আপনার কত বছরের অভিজ্ঞতা আছে?",
            "te": "{role}కి సంబంధించిన పనిలో మీకు ఎన్ని సంవత్సరాల అనుభవం ఉంది?",
            "pa": "{role} ਨਾਲ ਸਬੰਧਤ ਕੰਮ ਵਿੱਚ ਤੁਹਾਨੂੰ ਕਿੰਨੇ ਸਾਲ ਦਾ ਤਜਰਬਾ ਹੈ?",
            "gu": "{role} સંબંધિત કામમાં તમારી પાસે કેટલા વર્ષનો અનુભવ છે?",
        },
    },
    {
        "field": "experience",
        "prompts": {
            "en": "Where have you worked before? Please share your previous employer or work-site names and roughly how long you worked there.",
            "hi": "आपने पहले कहाँ काम किया है? कृपया अपने पिछले नियोक्ता या कार्य-स्थल के नाम और लगभग कितने समय तक काम किया, यह बताइए।",
            "bn": "আপনি আগে কোথায় কাজ করেছেন? অনুগ্রহ করে আপনার পূর্ববর্তী নিয়োগকর্তা বা কর্মস্থলের নাম এবং প্রায় কতদিন কাজ করেছেন তা জানান।",
            "te": "మీరు ఇంతకుముందు ఎక్కడ పనిచేశారు? దయచేసి మీ మునుపటి యజమాని లేదా పని ప్రదేశాల పేర్లు మరియు ఎంతకాలం పనిచేశారో చెప్పండి.",
            "pa": "ਤੁਸੀਂ ਪਹਿਲਾਂ ਕਿੱਥੇ ਕੰਮ ਕੀਤਾ ਹੈ? ਕਿਰਪਾ ਕਰਕੇ ਆਪਣੇ ਪਿਛਲੇ ਮਾਲਕ ਜਾਂ ਕੰਮ-ਥਾਂ ਦੇ ਨਾਮ ਅਤੇ ਲਗਭਗ ਕਿੰਨੇ ਸਮੇਂ ਲਈ ਕੰਮ ਕੀਤਾ, ਦੱਸੋ।",
            "gu": "તમે પહેલા ક્યાં કામ કર્યું છે? કૃપા કરીને તમારા અગાઉના નોકરીદાતા અથવા કાર્યસ્થળોના નામ અને લગભગ કેટલા સમય સુધી કામ કર્યું તે જણાવો.",
        },
    },
    {
        "field": "education",
        "prompts": {
            "en": "What is your educational background — for example, 10th pass, 12th, ITI diploma, or any other qualification?",
            "hi": "आपकी शैक्षणिक पृष्ठभूमि क्या है — जैसे 10वीं पास, 12वीं, आईटीआई डिप्लोमा, या कोई और योग्यता?",
            "bn": "আপনার শিক্ষাগত যোগ্যতা কী — যেমন দশম শ্রেণি পাস, দ্বাদশ, আইটিআই ডিপ্লোমা, অথবা অন্য কোনো যোগ্যতা?",
            "te": "మీ విద్యా అర్హత ఏమిటి — ఉదాహరణకు 10వ తరగతి, 12వ తరగతి, ITI డిప్లొమా, లేదా ఏదైనా ఇతర అర్హత?",
            "pa": "ਤੁਹਾਡੀ ਵਿਦਿਅਕ ਪਿਛੋਕੜ ਕੀ ਹੈ — ਜਿਵੇਂ ਕਿ 10ਵੀਂ ਪਾਸ, 12ਵੀਂ, ਆਈ.ਟੀ.ਆਈ. ਡਿਪਲੋਮਾ, ਜਾਂ ਕੋਈ ਹੋਰ ਯੋਗਤਾ?",
            "gu": "તમારી શૈક્ષણિક પૃષ્ઠભૂમિ શું છે — જેમ કે 10મું પાસ, 12મું, ITI ડિપ્લોમા, અથવા કોઈ અન્ય લાયકાત?",
        },
    },
    {
        "field": "salary",
        "prompts": {
            "en": "What monthly salary are you hoping for, and what was your last salary if you had one?",
            "hi": "आप कितनी मासिक तनख्वाह की उम्मीद रखते हैं, और अगर पहले काम किया है तो वहाँ कितनी तनख्वाह मिलती थी?",
            "bn": "আপনি মাসিক কত বেতনের আশা করছেন, এবং যদি আগে কাজ করে থাকেন তবে সেখানে কত বেতন পেতেন?",
            "te": "మీరు ఎంత నెలసరి జీతం ఆశిస్తున్నారు, మరియు మీరు ఇంతకుముందు పనిచేసి ఉంటే అక్కడ ఎంత జీతం వచ్చేది?",
            "pa": "ਤੁਸੀਂ ਮਹੀਨੇ ਦੀ ਕਿੰਨੀ ਤਨਖਾਹ ਦੀ ਉਮੀਦ ਰੱਖਦੇ ਹੋ, ਅਤੇ ਜੇ ਪਹਿਲਾਂ ਕੰਮ ਕੀਤਾ ਹੈ ਤਾਂ ਉੱਥੇ ਕਿੰਨੀ ਤਨਖਾਹ ਮਿਲਦੀ ਸੀ?",
            "gu": "તમે દર મહિને કેટલા પગારની અપેક્ષા રાખો છો, અને જો પહેલા કામ કર્યું હોય તો ત્યાં કેટલો પગાર મળતો હતો?",
        },
    },
    {
        "field": "availability",
        "prompts": {
            "en": "When can you start work, and are you willing to move to another city if needed?",
            "hi": "आप काम कब से शुरू कर सकते हैं, और अगर ज़रूरत पड़े तो क्या आप किसी दूसरे शहर जाने को तैयार हैं?",
            "bn": "আপনি কবে থেকে কাজ শুরু করতে পারবেন, এবং দরকার পড়লে কি অন্য শহরে যেতে রাজি আছেন?",
            "te": "మీరు ఎప్పటి నుండి పని ప్రారంభించగలరు, మరియు అవసరమైతే వేరే నగరానికి వెళ్లడానికి సిద్ధంగా ఉన్నారా?",
            "pa": "ਤੁਸੀਂ ਕੰਮ ਕਦੋਂ ਤੋਂ ਸ਼ੁਰੂ ਕਰ ਸਕਦੇ ਹੋ, ਅਤੇ ਜੇ ਲੋੜ ਪਵੇ ਤਾਂ ਕੀ ਤੁਸੀਂ ਕਿਸੇ ਹੋਰ ਸ਼ਹਿਰ ਜਾਣ ਲਈ ਤਿਆਰ ਹੋ?",
            "gu": "તમે કામ ક્યારથી શરૂ કરી શકો છો, અને જરૂર પડે તો શું તમે બીજા શહેરમાં જવા તૈયાર છો?",
        },
    },
]
