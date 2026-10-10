"""Multilingual patient portal: plain-language result explanations and discharge advice in English, Tamil and Hindi.

All text is a machine-drafted template that a clinician must approve before release to a patient.
"""

from __future__ import annotations

import re
from typing import Any

from . import terminology as T
from .chart import Chart
from .clinical import lab_flag

LANGS = {"en": "English", "ta": "தமிழ் (Tamil)", "hi": "हिन्दी (Hindi)"}

LAB_NAME = {
    "glucose": ("Blood sugar (glucose)", "இரத்த சர்க்கரை (குளுக்கோஸ்)", "ब्लड शुगर (ग्लूकोज़)"),
    "hba1c": ("3-month average sugar (HbA1c)", "3 மாத சராசரி சர்க்கரை (HbA1c)", "3 महीने का औसत शुगर (HbA1c)"),
    "creatinine": ("Kidney function marker (creatinine)", "சிறுநீரக செயல்பாட்டு அளவீடு (கிரியேட்டினின்)", "किडनी की जाँच (क्रिएटिनिन)"),
    "egfr": ("Kidney filtering rate (eGFR)", "சிறுநீரக வடிகட்டும் திறன் (eGFR)", "किडनी की छानने की क्षमता (eGFR)"),
    "potassium": ("Potassium", "பொட்டாசியம்", "पोटैशियम"),
    "sodium": ("Sodium", "சோடியம்", "सोडियम"),
    "wbc": ("White blood cells (infection fighters)", "வெள்ளை இரத்த அணுக்கள் (நோய் எதிர்ப்பு செல்கள்)", "श्वेत रक्त कोशिकाएँ (संक्रमण से लड़ने वाली)"),
    "hemoglobin": ("Haemoglobin (oxygen-carrying protein)", "ஹீமோகுளோபின் (ஆக்சிஜன் கொண்டு செல்லும் புரதம்)", "हीमोग्लोबिन (ऑक्सीजन ले जाने वाला प्रोटीन)"),
    "platelets": ("Platelets (help blood clot)", "பிளேட்லெட்டுகள் (இரத்தம் உறைய உதவும்)", "प्लेटलेट्स (खून जमाने में मदद करते हैं)"),
    "crp": ("CRP (inflammation marker)", "CRP (வீக்க அளவீடு)", "CRP (सूजन की जाँच)"),
    "lactate": ("Lactate", "லாக்டேட்", "लैक्टेट"),
    "troponin": ("Troponin (heart muscle marker)", "ட்ரோபோனின் (இதயத் தசை அளவீடு)", "ट्रोपोनिन (हृदय की मांसपेशी की जाँच)"),
    "ldl": ("LDL cholesterol ('bad' cholesterol)", "LDL கொலஸ்ட்ரால் ('கெட்ட' கொலஸ்ட்ரால்)", "LDL कोलेस्ट्रॉल ('खराब' कोलेस्ट्रॉल)"),
    "tsh": ("Thyroid signal (TSH)", "தைராய்டு அளவீடு (TSH)", "थायराइड की जाँच (TSH)"),
    "bnp": ("BNP (heart strain marker)", "BNP (இதய அழுத்த அளவீடு)", "BNP (हृदय पर दबाव की जाँच)"),
    "ddimer": ("D-dimer (clotting marker)", "D-dimer (இரத்த உறைவு அளவீடு)", "D-dimer (खून के थक्के की जाँच)"),
    "inr": ("INR (blood thinner test)", "INR (இரத்த உறைதல் பரிசோதனை)", "INR (खून पतला करने की दवा की जाँच)"),
}
IDX = {"en": 0, "ta": 1, "hi": 2}
STATUS = {
    "normal": ("This is in the normal range.", "இது சாதாரண அளவில் உள்ளது.", "यह सामान्य सीमा में है।"),
    "high": ("This is higher than normal.", "இது சாதாரணத்தை விட அதிகமாக உள்ளது.", "यह सामान्य से अधिक है।"),
    "low": ("This is lower than normal.", "இது சாதாரணத்தை விட குறைவாக உள்ளது.", "यह सामान्य से कम है।"),
    "critical-high": ("This is much higher than normal. Please tell your doctor or nurse today.", "இது சாதாரணத்தை விட மிகவும் அதிகமாக உள்ளது. இன்றே உங்கள் மருத்துவர் அல்லது செவிலியரிடம் தெரிவிக்கவும்.", "यह सामान्य से बहुत अधिक है। कृपया आज ही अपने डॉक्टर या नर्स को बताएँ।"),
    "critical-low": ("This is much lower than normal. Please tell your doctor or nurse today.", "இது சாதாரணத்தை விட மிகவும் குறைவாக உள்ளது. இன்றே உங்கள் மருத்துவர் அல்லது செவிலியரிடம் தெரிவிக்கவும்.", "यह सामान्य से बहुत कम है। कृपया आज ही अपने डॉक्टर या नर्स को बताएँ।"),
}
MEANING = {
    ("glucose", "high"): ("Your blood sugar is high, which can happen when diabetes is not well controlled.", "உங்கள் இரத்த சர்க்கரை அதிகமாக உள்ளது; நீரிழிவு சரியாகக் கட்டுப்படாதபோது இப்படி ஆகலாம்.", "आपका ब्लड शुगर अधिक है; मधुमेह ठीक से नियंत्रित न होने पर ऐसा हो सकता है।"),
    ("hba1c", "high"): ("This shows your sugar has been high over the last 3 months.", "கடந்த 3 மாதங்களாக உங்கள் சர்க்கரை அளவு அதிகமாக இருந்ததை இது காட்டுகிறது.", "यह दिखाता है कि पिछले 3 महीनों में आपका शुगर अधिक रहा है।"),
    ("creatinine", "high"): ("Your kidneys may not be filtering as well as they should. Some medicines may need a new dose.", "உங்கள் சிறுநீரகங்கள் வழக்கம்போல் வடிகட்டாமல் இருக்கலாம். சில மருந்துகளின் அளவை மாற்ற வேண்டியிருக்கலாம்.", "हो सकता है आपकी किडनी पहले जितनी अच्छी तरह छान न रही हो। कुछ दवाओं की मात्रा बदलनी पड़ सकती है।"),
    ("potassium", "high"): ("High potassium can affect the heartbeat, so your team will check it again.", "அதிக பொட்டாசியம் இதயத் துடிப்பைப் பாதிக்கலாம்; எனவே உங்கள் குழு மீண்டும் பரிசோதிக்கும்.", "अधिक पोटैशियम दिल की धड़कन को प्रभावित कर सकता है, इसलिए आपकी टीम इसे फिर जाँचेगी।"),
    ("hemoglobin", "low"): ("A low level means you may have anaemia, which can cause tiredness and breathlessness.", "குறைந்த அளவு என்றால் இரத்தசோகை இருக்கலாம்; அதனால் சோர்வு மற்றும் மூச்சுத் திணறல் ஏற்படலாம்.", "कम स्तर का मतलब खून की कमी हो सकती है, जिससे थकान और साँस फूलना हो सकता है।"),
    ("wbc", "high"): ("A high count often means your body is fighting an infection.", "அதிக எண்ணிக்கை பெரும்பாலும் உங்கள் உடல் தொற்றை எதிர்த்துப் போராடுவதைக் காட்டுகிறது.", "अधिक संख्या अक्सर बताती है कि आपका शरीर संक्रमण से लड़ रहा है।"),
    ("platelets", "low"): ("Low platelets can make bleeding easier, so avoid pain medicines like ibuprofen unless your doctor says it is safe.", "குறைந்த பிளேட்லெட்டுகள் இரத்தப்போக்கை எளிதாக்கலாம்; மருத்துவர் அனுமதிக்காத வரை இபுபுரூபன் போன்ற வலி மருந்துகளைத் தவிர்க்கவும்.", "कम प्लेटलेट्स से खून बहना आसान हो सकता है; डॉक्टर की अनुमति के बिना आइबुप्रोफेन जैसी दर्द की दवाएँ न लें।"),
    ("ldl", "high"): ("High 'bad' cholesterol raises the risk of heart disease. Diet, exercise and medicine can help.", "அதிக 'கெட்ட' கொலஸ்ட்ரால் இதய நோய் அபாயத்தை அதிகரிக்கும்; உணவு, உடற்பயிற்சி மற்றும் மருந்து உதவும்.", "अधिक 'खराब' कोलेस्ट्रॉल से हृदय रोग का खतरा बढ़ता है; आहार, व्यायाम और दवा से मदद मिलती है।"),
}
FREQ_TEXT = {1: ("once a day", "ஒரு நாளைக்கு ஒரு முறை", "दिन में एक बार"), 2: ("twice a day", "ஒரு நாளைக்கு இரண்டு முறை", "दिन में दो बार"), 3: ("three times a day", "ஒரு நாளைக்கு மூன்று முறை", "दिन में तीन बार"), 4: ("four times a day", "ஒரு நாளைக்கு நான்கு முறை", "दिन में चार बार")}
PURPOSE = {
    "bp": ("lowers blood pressure", "இரத்த அழுத்தத்தைக் குறைக்கும்", "ब्लड प्रेशर कम करती है"),
    "sugar": ("controls blood sugar", "இரத்த சர்க்கரையை கட்டுப்படுத்தும்", "ब्लड शुगर को नियंत्रित करती है"),
    "chol": ("lowers cholesterol", "கொலஸ்ட்ராலைக் குறைக்கும்", "कोलेस्ट्रॉल कम करती है"),
    "clot": ("prevents blood clots", "இரத்தம் உறைவதைத் தடுக்கும்", "खून के थक्के बनने से रोकती है"),
    "fluid": ("removes extra fluid", "உடலில் தேங்கிய நீரை வெளியேற்றும்", "शरीर से अतिरिक्त पानी निकालती है"),
    "heart": ("slows the heart and lowers blood pressure", "இதயத் துடிப்பைக் குறைத்து இரத்த அழுத்தத்தைக் குறைக்கும்", "दिल की धड़कन धीमी करती है और ब्लड प्रेशर कम करती है"),
    "abx": ("fights infection (antibiotic)", "தொற்றுக்கு எதிராகப் போராடும் (நுண்ணுயிர் எதிர்ப்பி)", "संक्रमण से लड़ती है (एंटीबायोटिक)"),
    "pain": ("reduces fever and pain", "காய்ச்சல் மற்றும் வலியைக் குறைக்கும்", "बुखार और दर्द कम करती है"),
    "airway": ("opens the airways", "சுவாசக் குழாய்களை விரிவாக்கும்", "साँस की नलियों को खोलती है"),
    "thin": ("thins the blood", "இரத்தத்தை இளக்கும்", "खून को पतला करती है"),
    "thyroid": ("replaces thyroid hormone", "தைராய்டு ஹார்மோனை ஈடுசெய்யும்", "थायराइड हार्मोन की कमी पूरी करती है"),
    "acid": ("reduces stomach acid", "வயிற்று அமிலத்தைக் குறைக்கும்", "पेट का एसिड कम करती है"),
    "inflam": ("reduces inflammation", "வீக்கத்தைக் குறைக்கும்", "सूजन कम करती है"),
    "digoxin": ("helps the heart beat steadily", "இதயம் சீராகத் துடிக்க உதவும்", "दिल को स्थिर धड़कने में मदद करती है"),
}
MED_PURPOSE = {"metformin": "sugar", "insulin_glargine": "sugar", "amlodipine": "bp", "telmisartan": "bp", "losartan": "bp", "lisinopril": "bp", "enalapril": "bp", "atorvastatin": "chol", "rosuvastatin": "chol",
               "aspirin": "clot", "clopidogrel": "clot", "furosemide": "fluid", "spironolactone": "fluid", "metoprolol": "heart", "ceftriaxone": "abx", "azithromycin": "abx", "amoxicillin": "abx", "amox_clav": "abx",
               "ciprofloxacin": "abx", "nitrofurantoin": "abx", "paracetamol": "pain", "salbutamol": "airway", "tiotropium": "airway", "warfarin": "thin", "enoxaparin": "thin", "levothyroxine": "thyroid",
               "pantoprazole": "acid", "omeprazole": "acid", "prednisolone": "inflam", "digoxin": "digoxin"}
GENERAL = ("Take your medicines exactly as prescribed and do not stop them without asking your doctor. Keep your follow-up appointment and bring this sheet and all your medicine strips.",
           "உங்கள் மருந்துகளை மருத்துவர் கூறியபடியே எடுத்துக்கொள்ளுங்கள்; மருத்துவரிடம் கேட்காமல் நிறுத்த வேண்டாம். தொடர் சிகிச்சை நேரத்தைத் தவறாமல் பின்பற்றுங்கள்; இந்தத் தாளையும் அனைத்து மருந்து அட்டைகளையும் கொண்டு வாருங்கள்.",
           "अपनी दवाएँ बिल्कुल डॉक्टर के बताए अनुसार लें और पूछे बिना बंद न करें। फॉलो-अप अपॉइंटमेंट पर आएँ और यह पर्चा तथा सभी दवाओं की पट्टियाँ साथ लाएँ।")
CONDITION_ADVICE: dict[str, tuple[tuple[str, str, str], tuple[str, str, str]]] = {
    "t2dm": (("Eat regular meals, cut down sugary food and drinks, and walk for 30 minutes most days.", "நேரத்துக்கு உணவு உண்ணுங்கள், இனிப்பு உணவு மற்றும் பானங்களைக் குறையுங்கள், வாரத்தில் பெரும்பாலான நாட்கள் 30 நிமிடம் நடக்கவும்.", "समय पर भोजन करें, मीठे खाने-पीने से बचें और ज़्यादातर दिन 30 मिनट टहलें।"),
             ("Seek help urgently for confusion, very high thirst and urination, vomiting, or a blood sugar below 70.", "குழப்பம், மிகுந்த தாகம் மற்றும் அதிக சிறுநீர், வாந்தி, அல்லது இரத்த சர்க்கரை 70-க்குக் குறைவாக இருந்தால் உடனே உதவி பெறுங்கள்.", "भ्रम, बहुत अधिक प्यास और पेशाब, उल्टी, या ब्लड शुगर 70 से कम होने पर तुरंत सहायता लें।")),
    "htn": (("Reduce salt, stay active and check your blood pressure at home if you can.", "உப்பைக் குறையுங்கள், சுறுசுறுப்பாக இருங்கள், முடிந்தால் வீட்டிலேயே இரத்த அழுத்தத்தைப் பரிசோதியுங்கள்.", "नमक कम करें, सक्रिय रहें और हो सके तो घर पर ब्लड प्रेशर जाँचें।"),
            ("Seek help urgently for a severe headache, chest pain, weakness on one side or trouble speaking.", "கடுமையான தலைவலி, நெஞ்சு வலி, ஒரு பக்க பலவீனம் அல்லது பேசுவதில் சிரமம் இருந்தால் உடனே உதவி பெறுங்கள்.", "तेज़ सिरदर्द, सीने में दर्द, एक तरफ कमज़ोरी या बोलने में कठिनाई होने पर तुरंत सहायता लें।")),
    "hf": (("Weigh yourself every morning, limit salt and fluids as advised, and rest with your head raised if you are breathless.", "தினமும் காலை எடை பாருங்கள், அறிவுறுத்தியபடி உப்பு மற்றும் திரவத்தைக் குறையுங்கள், மூச்சுத் திணறல் இருந்தால் தலையை உயர்த்தி ஓய்வெடுங்கள்.", "हर सुबह वज़न करें, सलाह के अनुसार नमक और तरल कम रखें, और साँस फूले तो सिर ऊँचा करके आराम करें।"),
           ("Seek help urgently if you gain more than 2 kg in 3 days, your legs swell more, or breathing gets worse.", "3 நாட்களில் 2 கிலோவுக்கு மேல் எடை கூடினாலோ, கால் வீக்கம் அதிகரித்தாலோ, மூச்சுத்திணறல் மோசமானாலோ உடனே உதவி பெறுங்கள்.", "3 दिनों में 2 किलो से अधिक वज़न बढ़ने, पैरों की सूजन बढ़ने या साँस लेने में परेशानी बढ़ने पर तुरंत सहायता लें।")),
    "cap": (("Finish the full antibiotic course, drink plenty of fluids and rest.", "நுண்ணுயிர் எதிர்ப்பி மருந்தை முழுவதுமாக முடியுங்கள், நிறைய திரவம் குடியுங்கள், ஓய்வெடுங்கள்.", "एंटीबायोटिक का पूरा कोर्स पूरा करें, खूब तरल पदार्थ पिएँ और आराम करें।"),
            ("Seek help urgently if breathing gets harder, fever returns, or you cough up blood.", "மூச்சு விடுவது கடினமானாலோ, காய்ச்சல் மீண்டும் வந்தாலோ, இருமலில் இரத்தம் வந்தாலோ உடனே உதவி பெறுங்கள்.", "साँस लेना कठिन होने, बुखार वापस आने या खाँसी में खून आने पर तुरंत सहायता लें।")),
    "dengue": (("Rest, drink oral fluids often, and use paracetamol only for fever. Do not take aspirin or ibuprofen.", "ஓய்வெடுங்கள், அடிக்கடி திரவம் குடியுங்கள், காய்ச்சலுக்கு பாராசிட்டமால் மட்டும் பயன்படுத்துங்கள். ஆஸ்பிரின் அல்லது இபுபுரூபன் எடுக்க வேண்டாம்.", "आराम करें, बार-बार तरल पदार्थ पिएँ और बुखार के लिए केवल पैरासिटामोल लें। एस्पिरिन या आइबुप्रोफेन न लें।"),
               ("Seek help urgently for bleeding, black stools, severe belly pain, repeated vomiting or extreme drowsiness.", "இரத்தப்போக்கு, கருப்பு மலம், கடுமையான வயிற்று வலி, தொடர் வாந்தி அல்லது அதிக தூக்கக் கலக்கம் இருந்தால் உடனே உதவி பெறுங்கள்.", "खून बहने, काले मल, पेट में तेज़ दर्द, बार-बार उल्टी या अत्यधिक सुस्ती होने पर तुरंत सहायता लें।")),
    "copd": (("Do not smoke, use your inhalers as shown, and keep your vaccinations up to date.", "புகைபிடிக்க வேண்டாம், இன்ஹேலர்களைக் காட்டியபடி பயன்படுத்துங்கள், தடுப்பூசிகளைத் தவறாமல் போட்டுக்கொள்ளுங்கள்.", "धूम्रपान न करें, इनहेलर बताए अनुसार इस्तेमाल करें और टीके समय पर लगवाएँ।"),
             ("Seek help urgently if your lips look blue, breathing is much worse, or you feel very drowsy.", "உதடுகள் நீல நிறமானாலோ, மூச்சுத்திணறல் மிகவும் மோசமானாலோ, மிகவும் தூக்கக் கலக்கம் இருந்தாலோ உடனே உதவி பெறுங்கள்.", "होंठ नीले दिखने, साँस बहुत ख़राब होने या बहुत अधिक सुस्ती होने पर तुरंत सहायता लें।")),
    "stroke": (("Take your blood thinner and cholesterol medicines every day, and follow your therapy plan.", "இரத்தம் இளக்கும் மற்றும் கொலஸ்ட்ரால் மருந்துகளை தினமும் எடுத்துக்கொள்ளுங்கள்; சிகிச்சைத் திட்டத்தைப் பின்பற்றுங்கள்.", "ख़ून पतला करने वाली और कोलेस्ट्रॉल की दवाएँ रोज़ लें और थेरेपी योजना का पालन करें।"),
               ("Call emergency services at once for face drooping, arm weakness or speech trouble.", "முகம் ஒரு பக்கம் சாய்தல், கை பலவீனம் அல்லது பேசுவதில் சிரமம் இருந்தால் உடனே அவசர உதவியை அழையுங்கள்.", "चेहरा एक तरफ झुकने, बाँह में कमज़ोरी या बोलने में कठिनाई होने पर तुरंत आपातकालीन सहायता बुलाएँ।")),
    "mi": (("Take your heart medicines daily, avoid heavy exertion for now, and join cardiac rehabilitation.", "இதய மருந்துகளை தினமும் எடுத்துக்கொள்ளுங்கள், இப்போதைக்கு கடின உழைப்பைத் தவிருங்கள், இதய மறுவாழ்வில் சேருங்கள்.", "हृदय की दवाएँ रोज़ लें, अभी भारी मेहनत से बचें और कार्डियक रिहैबिलिटेशन में शामिल हों।"),
           ("Call emergency services at once for chest pain, sweating or breathlessness that does not settle.", "நெஞ்சு வலி, வியர்வை அல்லது குறையாத மூச்சுத்திணறல் இருந்தால் உடனே அவசர உதவியை அழையுங்கள்.", "सीने में दर्द, पसीना या न रुकने वाली साँस फूलने पर तुरंत आपातकालीन सहायता बुलाएँ।")),
    "ckd3": (("Drink fluids as advised, avoid pain medicines like ibuprofen, and have your kidney tests on schedule.", "அறிவுறுத்தியபடி திரவம் குடியுங்கள், இபுபுரூபன் போன்ற வலி மருந்துகளைத் தவிருங்கள், சிறுநீரகப் பரிசோதனைகளை நேரத்துக்குச் செய்யுங்கள்.", "सलाह के अनुसार तरल पदार्थ लें, आइबुप्रोफेन जैसी दर्द की दवाओं से बचें और किडनी की जाँच समय पर कराएँ।"),
             ("Seek help if you pass very little urine, have new swelling, or feel very weak.", "மிகக் குறைவாக சிறுநீர் கழித்தாலோ, புதிய வீக்கம் இருந்தாலோ, மிகவும் பலவீனமாக உணர்ந்தாலோ உதவி பெறுங்கள்.", "बहुत कम पेशाब होने, नई सूजन आने या बहुत कमज़ोरी महसूस होने पर सहायता लें।")),
}
SECTION = {"results": ("Your test results", "உங்கள் பரிசோதனை முடிவுகள்", "आपकी जाँच के नतीजे"), "medicines": ("Your medicines", "உங்கள் மருந்துகள்", "आपकी दवाएँ"),
           "advice": ("Looking after yourself", "உங்களைப் பராமரித்தல்", "अपना ध्यान रखें"), "warning": ("When to get help straight away", "உடனே உதவி பெற வேண்டிய நேரங்கள்", "कब तुरंत सहायता लें")}
DISCLAIMER = ("Draft generated by software for your care team to review. It does not replace advice from your doctor.", "இது உங்கள் மருத்துவக் குழு சரிபார்ப்பதற்காக மென்பொருளால் உருவாக்கப்பட்ட வரைவு. உங்கள் மருத்துவரின் ஆலோசனைக்கு மாற்று அல்ல.", "यह आपकी देखभाल टीम की समीक्षा के लिए सॉफ़्टवेयर द्वारा बनाया गया मसौदा है। यह आपके डॉक्टर की सलाह का विकल्प नहीं है।")


def _syllables(word: str) -> int:
    word = word.lower()
    groups = re.findall(r"[aeiouy]+", word)
    n = len(groups)
    if word.endswith("e") and n > 1:
        n -= 1
    return max(n, 1)


def readability(text: str, lang: str) -> dict[str, Any]:
    sentences = [s for s in re.split(r"[.!?।]+", text) if s.strip()]
    words = re.findall(r"\w+", text, flags=re.UNICODE)
    avg = len(words) / max(len(sentences), 1)
    out: dict[str, Any] = {"sentences": len(sentences), "words": len(words), "avg_sentence_words": round(avg, 1)}
    if lang == "en":
        syl = sum(_syllables(w) for w in words if w.isalpha())
        grade = 0.39 * avg + 11.8 * (syl / max(len(words), 1)) - 15.59
        out["flesch_kincaid_grade"] = round(max(grade, 1), 1)
    else:
        out["note"] = "Grade-level formulas are not validated for this language; average sentence length is shown instead."
    return out


def build(chart: Chart, lang: str = "en", level: str = "simple") -> dict[str, Any]:
    if lang not in LANGS:
        raise ValueError(f"lang must be one of {list(LANGS)}")
    i = IDX[lang]
    results = []
    for key, rows in chart.labs.items():
        if key not in LAB_NAME:
            continue
        t, val, _ = rows[-1]
        flag = lab_flag(key, val, chart.sex)
        unit = T.LABS[key]["unit"]
        line = f"{LAB_NAME[key][i]}: {val:g} {unit}. {STATUS[flag][i]}"
        item = {"key": key, "name": LAB_NAME[key][i], "value": val, "unit": unit, "flag": flag, "date": t[:10], "text": line}
        if level == "standard" and (key, "high" if "high" in flag else "low") in MEANING and flag != "normal":
            item["meaning"] = MEANING[(key, "high" if "high" in flag else "low")][i]
            item["text"] += " " + item["meaning"]
        results.append(item)
    results.sort(key=lambda r: (r["flag"] == "normal", r["key"]))
    meds = []
    for m in chart.meds:
        if m["status"] != "active" or not m["key"]:
            continue
        pk = MED_PURPOSE.get(m["key"])
        freq = None
        for token, n in (("QID", 4), ("TDS", 3), ("BD", 2), ("once daily", 1), ("at night", 1)):
            if token.lower() in m["sig"].lower():
                freq = n
                break
        dose = re.search(r"\d+(?:\.\d+)?\s?(?:mg|mcg|g|units)", m["sig"])
        prn = "prn" in m["sig"].lower()
        text = f"{m['display'].split(' (')[0]}" + (f" {dose.group(0)}" if dose else "") + (f", {FREQ_TEXT[freq][i]}" if freq else "") + (f" ({'as needed' if lang == 'en' else 'தேவைப்படும்போது' if lang == 'ta' else 'ज़रूरत पड़ने पर'})" if prn else "")
        meds.append({"name": m["display"], "text": text + (f": {PURPOSE[pk][i]}." if pk else "."), "purpose": PURPOSE[pk][i] if pk else None})
    advice, warnings = [GENERAL[i]], []
    for c in chart.conditions:
        if c["key"] in CONDITION_ADVICE:
            a, w = CONDITION_ADVICE[c["key"]]
            if a[i] not in advice:
                advice.append(a[i])
            if w[i] not in warnings:
                warnings.append(w[i])
    body = " ".join([r["text"] for r in results] + [m["text"] for m in meds] + advice + warnings)
    return {"patient": chart.pid, "language": lang, "language_name": LANGS[lang], "level": level,
            "sections": {"results": {"title": SECTION["results"][i], "items": results}, "medicines": {"title": SECTION["medicines"][i], "items": meds},
                         "advice": {"title": SECTION["advice"][i], "items": advice}, "warning": {"title": SECTION["warning"][i], "items": warnings}},
            "disclaimer": DISCLAIMER[i], "readability": readability(body, lang), "review_status": "draft",
            "requires_clinician_approval": True}
