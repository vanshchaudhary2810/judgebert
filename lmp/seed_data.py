"""Parallel English-Hindi seed corpus of legal clauses (insurance + tenancy).

Each concept has, for both languages:
    context  - the definition / heading that precedes the clause in the document
    original - the clause in formal legal language
    simple   - a hand-written, meaning-preserving plain-language simplification

These clauses were written for this project in the style of Indian insurance policies
and residential rent agreements (they are not copied from any real document).

IMPORTANT: this seed corpus + the rule-based perturbations in `perturb.py` produce
*silver* LMP labels. They let you run and debug the whole pipeline today and are useful
as data augmentation, but the research results in your paper must come from the
human-annotated dataset (see `annotation_template.csv` and `data.load_annotated_csv`).
"""

SEED = [
    # ============================ INSURANCE ============================
    {
        "cid": "INS01", "domain": "insurance",
        "en": (
            "Definitions: 'Loss' means any physical loss of or damage to the insured property during the period of insurance.",
            "The Insured shall notify the Insurer in writing of any loss within 30 days of its occurrence, failing which the claim shall not be admissible.",
            "The insured must tell the insurer in writing about any loss within 30 days. Otherwise, the claim will not be accepted.",
        ),
        "hi": (
            "परिभाषाएँ: 'हानि' का अर्थ बीमा अवधि के दौरान बीमित संपत्ति की कोई भी भौतिक हानि या क्षति है।",
            "बीमाधारक किसी भी हानि के घटित होने के 30 दिनों के भीतर बीमाकर्ता को लिखित रूप में सूचित करेगा, अन्यथा दावा स्वीकार्य नहीं होगा।",
            "बीमाधारक को किसी भी नुकसान की जानकारी 30 दिनों के अंदर बीमाकर्ता को लिखकर देनी होगी। ऐसा न करने पर दावा स्वीकार नहीं होगा।",
        ),
    },
    {
        "cid": "INS02", "domain": "insurance",
        "en": (
            "Section II lists the optional extensions available under this Policy, including the Flood Extension.",
            "The Insurer shall not be liable for any loss or damage caused by flood, unless the Flood Extension has been purchased and the additional premium paid.",
            "The insurer will not pay for flood damage unless you bought the Flood Extension and paid the extra premium.",
        ),
        "hi": (
            "खंड II में इस पॉलिसी के अंतर्गत उपलब्ध वैकल्पिक विस्तार सूचीबद्ध हैं, जिनमें बाढ़ विस्तार शामिल है।",
            "बीमाकर्ता बाढ़ से हुई किसी भी हानि या क्षति के लिए उत्तरदायी नहीं होगा, सिवाय इसके कि बाढ़ विस्तार कवर खरीदा गया हो और अतिरिक्त प्रीमियम का भुगतान किया गया हो।",
            "बीमाकर्ता बाढ़ से हुए नुकसान का भुगतान नहीं करेगा, सिवाय इसके कि आपने बाढ़ विस्तार कवर खरीदा हो और अतिरिक्त प्रीमियम चुकाया हो।",
        ),
    },
    {
        "cid": "INS03", "domain": "insurance",
        "en": (
            "'Replacement value' means the cost of replacing the property with new property of the same kind and capacity.",
            "Where the sum insured is less than 80 percent of the replacement value of the property, the indemnity payable shall be reduced proportionately.",
            "If the sum insured is less than 80% of the replacement value, the payment will be reduced proportionately.",
        ),
        "hi": (
            "'प्रतिस्थापन मूल्य' का अर्थ संपत्ति को उसी प्रकार और क्षमता की नई संपत्ति से बदलने की लागत है।",
            "जहाँ बीमित राशि संपत्ति के प्रतिस्थापन मूल्य के 80 प्रतिशत से कम है, वहाँ देय क्षतिपूर्ति आनुपातिक रूप से घटा दी जाएगी।",
            "यदि बीमित राशि प्रतिस्थापन मूल्य के 80% से कम है, तो भुगतान उसी अनुपात में कम कर दिया जाएगा।",
        ),
    },
    {
        "cid": "INS04", "domain": "insurance",
        "en": (
            "The period of insurance is the twelve-month period stated in the Schedule.",
            "The policyholder shall pay the premium in full prior to the commencement of the period of insurance, and no cover shall attach until such payment is received.",
            "The policyholder must pay the full premium before the policy starts. There is no cover until the payment is received.",
        ),
        "hi": (
            "बीमा अवधि अनुसूची में उल्लिखित बारह माह की अवधि है।",
            "पॉलिसीधारक बीमा अवधि के प्रारंभ से पूर्व प्रीमियम का पूर्ण भुगतान करेगा, और ऐसा भुगतान प्राप्त होने तक कोई कवर लागू नहीं होगा।",
            "पॉलिसीधारक को पॉलिसी शुरू होने से पहले पूरा प्रीमियम चुकाना होगा। भुगतान मिलने तक कोई कवर नहीं होगा।",
        ),
    },
    {
        "cid": "INS05", "domain": "insurance",
        "en": (
            "This Section covers loss of or damage to the insured property by burglary or theft.",
            "In the event of theft, the Insured must lodge a First Information Report with the police within 48 hours and furnish a copy thereof to the Insurer.",
            "If something is stolen, the insured must file an FIR with the police within 48 hours and give a copy to the insurer.",
        ),
        "hi": (
            "यह खंड सेंधमारी या चोरी द्वारा बीमित संपत्ति की हानि या क्षति को कवर करता है।",
            "चोरी की स्थिति में, बीमाधारक 48 घंटों के भीतर पुलिस में प्रथम सूचना रिपोर्ट दर्ज कराएगा और उसकी एक प्रति बीमाकर्ता को प्रस्तुत करेगा।",
            "यदि कुछ चोरी हो जाए, तो बीमाधारक को 48 घंटों के अंदर पुलिस में FIR दर्ज करानी होगी और उसकी कॉपी बीमाकर्ता को देनी होगी।",
        ),
    },
    {
        "cid": "INS06", "domain": "insurance",
        "en": (
            "General Conditions: the following conditions apply to all Sections of this Policy.",
            "The Insurer may cancel this Policy by giving 15 days' notice in writing to the Insured, in which event a pro-rata refund of premium shall be made.",
            "The insurer may cancel this policy by giving the insured 15 days' written notice. The insurer must then refund part of the premium.",
        ),
        "hi": (
            "सामान्य शर्तें: निम्नलिखित शर्तें इस पॉलिसी के सभी खंडों पर लागू होती हैं।",
            "बीमाकर्ता बीमाधारक को 15 दिनों का लिखित नोटिस देकर इस पॉलिसी को रद्द कर सकता है, जिस स्थिति में प्रीमियम की आनुपातिक वापसी की जाएगी।",
            "बीमाकर्ता बीमाधारक को 15 दिन का लिखित नोटिस देकर यह पॉलिसी रद्द कर सकता है। तब बीमाकर्ता को प्रीमियम का कुछ हिस्सा लौटाना होगा।",
        ),
    },
    {
        "cid": "INS07", "domain": "insurance",
        "en": (
            "Section I covers accidental loss of or damage to the insured property, subject to the exclusions below.",
            "No claim shall be payable in respect of any loss arising from wear and tear, gradual deterioration or mechanical breakdown.",
            "The policy does not pay for any loss caused by wear and tear, slow deterioration or mechanical breakdown.",
        ),
        "hi": (
            "खंड I नीचे दिए गए अपवादों के अधीन बीमित संपत्ति की आकस्मिक हानि या क्षति को कवर करता है।",
            "टूट-फूट, क्रमिक क्षय या यांत्रिक खराबी से उत्पन्न किसी भी हानि के संबंध में कोई दावा देय नहीं होगा।",
            "पॉलिसी टूट-फूट, धीरे-धीरे खराब होने या मशीनी खराबी से हुए किसी भी नुकसान का भुगतान नहीं करती है।",
        ),
    },
    {
        "cid": "INS08", "domain": "insurance",
        "en": (
            "General Conditions: the following conditions apply to all Sections of this Policy.",
            "The Insured shall take all reasonable steps to safeguard the insured property from loss or damage, and failure to do so may result in the claim being reduced.",
            "The insured must take all reasonable steps to protect the property. If not, the claim may be reduced.",
        ),
        "hi": (
            "सामान्य शर्तें: निम्नलिखित शर्तें इस पॉलिसी के सभी खंडों पर लागू होती हैं।",
            "बीमाधारक बीमित संपत्ति को हानि या क्षति से बचाने के लिए सभी उचित कदम उठाएगा, और ऐसा न करने पर दावे की राशि घटाई जा सकती है।",
            "बीमाधारक को संपत्ति की सुरक्षा के लिए सभी उचित कदम उठाने होंगे। ऐसा न करने पर दावा कम किया जा सकता है।",
        ),
    },
    {
        "cid": "INS09", "domain": "insurance",
        "en": (
            "'Sum Insured' means the amount stated in the Schedule against each Section.",
            "The maximum liability of the Insurer under this Policy shall not exceed the Sum Insured of Rs. 5,00,000 for any one occurrence.",
            "The insurer will pay at most Rs. 5,00,000 for any one event.",
        ),
        "hi": (
            "'बीमित राशि' का अर्थ अनुसूची में प्रत्येक खंड के सामने उल्लिखित राशि है।",
            "इस पॉलिसी के अंतर्गत बीमाकर्ता का अधिकतम दायित्व किसी एक घटना के लिए रु. 5,00,000 की बीमित राशि से अधिक नहीं होगा।",
            "बीमाकर्ता किसी एक घटना के लिए अधिकतम रु. 5,00,000 तक का भुगतान करेगा।",
        ),
    },
    {
        "cid": "INS10", "domain": "insurance",
        "en": (
            "Arbitration under this Policy is governed by the Arbitration and Conciliation Act.",
            "Any dispute regarding the quantum of loss shall be referred to arbitration, provided that the Insurer has admitted liability under this Policy.",
            "Any dispute about the amount of loss must go to arbitration, provided the insurer has accepted liability.",
        ),
        "hi": (
            "इस पॉलिसी के अंतर्गत मध्यस्थता माध्यस्थम् और सुलह अधिनियम द्वारा शासित है।",
            "हानि की मात्रा के संबंध में कोई भी विवाद मध्यस्थता को भेजा जाएगा, बशर्ते बीमाकर्ता ने इस पॉलिसी के अंतर्गत दायित्व स्वीकार किया हो।",
            "नुकसान की राशि पर कोई भी विवाद मध्यस्थता में जाएगा, बशर्ते बीमाकर्ता ने दायित्व स्वीकार किया हो।",
        ),
    },
    {
        "cid": "INS11", "domain": "insurance",
        "en": (
            "'Deductible' means the amount of each claim that the Insured must bear before the Insurer pays.",
            "The deductible of Rs. 10,000 shall be borne by the Insured in respect of each and every claim.",
            "The insured must pay the first Rs. 10,000 of each claim.",
        ),
        "hi": (
            "'कटौती राशि' का अर्थ प्रत्येक दावे की वह राशि है जो बीमाकर्ता के भुगतान से पहले बीमाधारक को वहन करनी होती है।",
            "प्रत्येक दावे के संबंध में रु. 10,000 की कटौती राशि बीमाधारक द्वारा वहन की जाएगी।",
            "हर दावे के पहले रु. 10,000 बीमाधारक को खुद चुकाने होंगे।",
        ),
    },
    {
        "cid": "INS12", "domain": "insurance",
        "en": (
            "'Insured vehicle' means the vehicle described in the Schedule of this Policy.",
            "This Policy shall automatically terminate upon the sale or transfer of the insured vehicle, unless the Insurer's prior written consent has been obtained.",
            "This policy ends automatically when the vehicle is sold or transferred, unless the insurer agreed in writing beforehand.",
        ),
        "hi": (
            "'बीमित वाहन' का अर्थ इस पॉलिसी की अनुसूची में वर्णित वाहन है।",
            "बीमित वाहन की बिक्री या हस्तांतरण पर यह पॉलिसी स्वतः समाप्त हो जाएगी, जब तक कि बीमाकर्ता की पूर्व लिखित सहमति प्राप्त न की गई हो।",
            "वाहन बेचने या हस्तांतरित करने पर यह पॉलिसी अपने आप खत्म हो जाएगी, जब तक कि बीमाकर्ता ने पहले लिखित में सहमति न दी हो।",
        ),
    },
    # ============================ TENANCY ============================
    {
        "cid": "TEN01", "domain": "tenancy",
        "en": (
            "This Rent Agreement is made between the Landlord and the Tenant for the premises described in Schedule A.",
            "The Tenant shall pay the monthly rent of Rs. 25,000 on or before the 5th day of each calendar month.",
            "The tenant must pay the monthly rent of Rs. 25,000 by the 5th of every month.",
        ),
        "hi": (
            "यह किराया अनुबंध अनुसूची क में वर्णित परिसर के लिए मकान-मालिक और किरायेदार के बीच किया गया है।",
            "किरायेदार प्रत्येक कैलेंडर माह की 5 तारीख को या उससे पूर्व रु. 25,000 का मासिक किराया अदा करेगा।",
            "किरायेदार को हर महीने की 5 तारीख तक रु. 25,000 मासिक किराया देना होगा।",
        ),
    },
    {
        "cid": "TEN02", "domain": "tenancy",
        "en": (
            "'Premises' means the residential flat described in Schedule A, including fittings and fixtures.",
            "The Tenant shall not sublet, assign or part with possession of the premises or any part thereof without the prior written consent of the Landlord.",
            "The tenant must not sublet or hand over any part of the premises without the landlord's written permission first.",
        ),
        "hi": (
            "'परिसर' का अर्थ अनुसूची क में वर्णित आवासीय फ्लैट है, जिसमें फिटिंग और फिक्स्चर शामिल हैं।",
            "किरायेदार मकान-मालिक की पूर्व लिखित सहमति के बिना परिसर या उसके किसी भाग को उप-किराये पर नहीं देगा, न ही उसका कब्ज़ा किसी अन्य को सौंपेगा।",
            "किरायेदार मकान-मालिक की लिखित अनुमति के बिना परिसर का कोई भी हिस्सा किसी और को किराये पर नहीं दे सकता।",
        ),
    },
    {
        "cid": "TEN03", "domain": "tenancy",
        "en": (
            "The Tenant has paid a security deposit to the Landlord at the time of signing this agreement.",
            "The security deposit of Rs. 1,00,000 shall be refunded by the Landlord within 30 days of the Tenant vacating the premises, after deducting any arrears of rent.",
            "The landlord must return the Rs. 1,00,000 security deposit within 30 days after the tenant leaves, minus any unpaid rent.",
        ),
        "hi": (
            "किरायेदार ने इस अनुबंध पर हस्ताक्षर के समय मकान-मालिक को प्रतिभूति राशि का भुगतान किया है।",
            "मकान-मालिक, किरायेदार द्वारा परिसर खाली किए जाने के 30 दिनों के भीतर, किराये के बकाया की कटौती के पश्चात रु. 1,00,000 की प्रतिभूति राशि वापस करेगा।",
            "किरायेदार के घर खाली करने के 30 दिनों के अंदर मकान-मालिक को रु. 1,00,000 की सिक्योरिटी राशि लौटानी होगी, बकाया किराया काटकर।",
        ),
    },
    {
        "cid": "TEN04", "domain": "tenancy",
        "en": (
            "Termination: this clause sets out how the agreement may be ended before its expiry.",
            "Either party may terminate this agreement by giving the other party not less than two months' notice in writing.",
            "Either side can end this agreement by giving the other at least two months' written notice.",
        ),
        "hi": (
            "समाप्ति: यह खंड बताता है कि अनुबंध को उसकी अवधि पूरी होने से पहले कैसे समाप्त किया जा सकता है।",
            "कोई भी पक्ष दूसरे पक्ष को कम से कम दो माह का लिखित नोटिस देकर इस अनुबंध को समाप्त कर सकता है।",
            "कोई भी पक्ष दूसरे पक्ष को कम से कम दो महीने का लिखित नोटिस देकर यह अनुबंध खत्म कर सकता है।",
        ),
    },
    {
        "cid": "TEN05", "domain": "tenancy",
        "en": (
            "The monthly rent payable under this agreement is stated in Clause 2.",
            "The rent shall be increased by 5 percent upon the expiry of every eleven months, unless otherwise agreed between the parties in writing.",
            "The rent will go up by 5% every eleven months, unless both sides agree otherwise in writing.",
        ),
        "hi": (
            "इस अनुबंध के अंतर्गत देय मासिक किराया खंड 2 में उल्लिखित है।",
            "प्रत्येक ग्यारह माह की समाप्ति पर किराये में 5 प्रतिशत की वृद्धि की जाएगी, जब तक कि पक्षकारों के बीच लिखित रूप में अन्यथा सहमति न हो।",
            "हर ग्यारह महीने बाद किराया 5% बढ़ेगा, जब तक कि दोनों पक्ष लिखित में कुछ और तय न करें।",
        ),
    },
    {
        "cid": "TEN06", "domain": "tenancy",
        "en": (
            "Maintenance and Repairs.",
            "The Landlord shall be responsible for all major structural repairs, whereas minor day-to-day repairs shall be carried out by the Tenant at his own cost.",
            "The landlord must handle all major structural repairs. The tenant must pay for small everyday repairs.",
        ),
        "hi": (
            "रखरखाव और मरम्मत।",
            "मकान-मालिक सभी बड़ी संरचनात्मक मरम्मत के लिए उत्तरदायी होगा, जबकि छोटी दैनिक मरम्मत किरायेदार द्वारा अपने व्यय पर कराई जाएगी।",
            "सभी बड़ी संरचनात्मक मरम्मत मकान-मालिक को करानी होगी। छोटी रोज़मर्रा की मरम्मत का खर्च किरायेदार को उठाना होगा।",
        ),
    },
    {
        "cid": "TEN07", "domain": "tenancy",
        "en": (
            "Landlord's Rights.",
            "The Landlord or his authorised agent may enter the premises for inspection upon giving the Tenant at least 24 hours' prior notice.",
            "The landlord or his agent can enter the premises for inspection if he gives the tenant at least 24 hours' notice.",
        ),
        "hi": (
            "मकान-मालिक के अधिकार।",
            "मकान-मालिक या उसका अधिकृत एजेंट किरायेदार को कम से कम 24 घंटे का पूर्व नोटिस देकर निरीक्षण हेतु परिसर में प्रवेश कर सकता है।",
            "अगर मकान-मालिक किरायेदार को कम से कम 24 घंटे पहले बता दे, तो वह या उसका एजेंट जाँच के लिए परिसर में आ सकता है।",
        ),
    },
    {
        "cid": "TEN08", "domain": "tenancy",
        "en": (
            "Use of Premises.",
            "The premises shall be used solely for residential purposes and the Tenant shall not carry on any commercial activity therein.",
            "The premises must be used only as a home. The tenant must not run any business there.",
        ),
        "hi": (
            "परिसर का उपयोग।",
            "परिसर का उपयोग केवल आवासीय प्रयोजनों हेतु किया जाएगा और किरायेदार उसमें कोई वाणिज्यिक गतिविधि नहीं करेगा।",
            "परिसर का उपयोग केवल रहने के लिए करना होगा। किरायेदार वहाँ कोई व्यापार नहीं कर सकता।",
        ),
    },
    {
        "cid": "TEN09", "domain": "tenancy",
        "en": (
            "Default and Remedies.",
            "In case of default in payment of rent for two consecutive months, the Landlord shall be entitled to terminate the tenancy forthwith.",
            "If the tenant does not pay rent for two months in a row, the landlord can end the tenancy immediately.",
        ),
        "hi": (
            "चूक और उपचार।",
            "लगातार दो माह तक किराये के भुगतान में चूक होने की स्थिति में, मकान-मालिक तत्काल किरायेदारी समाप्त करने का हकदार होगा।",
            "यदि किरायेदार लगातार दो महीने किराया नहीं देता, तो मकान-मालिक तुरंत किरायेदारी खत्म कर सकता है।",
        ),
    },
    {
        "cid": "TEN10", "domain": "tenancy",
        "en": (
            "Utilities and Other Charges.",
            "The Tenant shall bear the electricity and water charges as per actual consumption, as recorded by the separate meters installed in the premises.",
            "The tenant must pay the electricity and water bills based on actual use, as shown by the separate meters.",
        ),
        "hi": (
            "उपयोगिताएँ और अन्य शुल्क।",
            "किरायेदार परिसर में लगे अलग मीटरों द्वारा दर्ज वास्तविक खपत के अनुसार बिजली और पानी के शुल्क वहन करेगा।",
            "किरायेदार को अलग मीटरों में दर्ज असली खपत के हिसाब से बिजली और पानी का बिल चुकाना होगा।",
        ),
    },
    {
        "cid": "TEN11", "domain": "tenancy",
        "en": (
            "Term of Agreement.",
            "This agreement shall be for a period of eleven months commencing from 1st April 2026, and may be renewed by mutual consent of the parties.",
            "This agreement lasts eleven months starting 1 April 2026. It can be renewed if both sides agree.",
        ),
        "hi": (
            "अनुबंध की अवधि।",
            "यह अनुबंध 1 अप्रैल 2026 से प्रारंभ होकर ग्यारह माह की अवधि के लिए होगा, और पक्षकारों की आपसी सहमति से नवीनीकृत किया जा सकता है।",
            "यह अनुबंध 1 अप्रैल 2026 से ग्यारह महीने के लिए है। दोनों पक्ष सहमत हों तो इसे आगे बढ़ाया जा सकता है।",
        ),
    },
    {
        "cid": "TEN12", "domain": "tenancy",
        "en": (
            "Handing Over of Possession.",
            "The Tenant shall hand over vacant and peaceful possession of the premises to the Landlord upon expiry or earlier termination of this agreement, failing which he shall be liable to pay double the monthly rent as damages.",
            "When the agreement ends, the tenant must give the empty premises back to the landlord. If he does not, he must pay double the monthly rent as damages.",
        ),
        "hi": (
            "कब्ज़ा सौंपना।",
            "इस अनुबंध की समाप्ति या पूर्व समापन पर किरायेदार परिसर का खाली और शांतिपूर्ण कब्ज़ा मकान-मालिक को सौंपेगा, ऐसा न करने पर वह हर्जाने के रूप में मासिक किराये का दोगुना भुगतान करने का दायी होगा।",
            "अनुबंध खत्म होने पर किरायेदार को खाली घर मकान-मालिक को लौटाना होगा। ऐसा न करने पर उसे हर्जाने के रूप में दोगुना मासिक किराया देना होगा।",
        ),
    },
]


def seed_rows():
    """Flatten SEED into rows: one per (concept, language)."""
    rows = []
    for item in SEED:
        for lang in ("en", "hi"):
            ctx, orig, simp = item[lang]
            rows.append({
                "source_id": f"{item['cid']}-{lang}",
                "concept_id": item["cid"],
                "domain": item["domain"],
                "lang": lang,
                "context": ctx,
                "original": orig,
                "faithful": simp,
            })
    return rows
