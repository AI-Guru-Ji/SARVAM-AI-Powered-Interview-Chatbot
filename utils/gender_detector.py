"""
gender_detector.py — Heuristic gender lookup for Indian first names.

The dicebear ``avataaars`` style picks long-hair variants randomly based
on seed, which makes male candidates show up with feminine avatars
during demos. This module returns ``"male"`` / ``"female"`` / ``"unknown"``
so we can pick gender-appropriate hair/facial-hair options.

The lists are intentionally narrow — common, single-token Indian first
names. Anything unrecognised returns ``"unknown"`` and the caller uses a
gender-neutral avatar (no styling forced either way).
"""

from __future__ import annotations


_MALE_NAMES: frozenset[str] = frozenset({
    # ── Classic Sanskrit / Hindi ──────────────────────────────────────
    "aakash", "aarav", "aaryan", "abhay", "abhinav", "abhishek", "ankur",
    "birjesh", "bunty", "chintu", "guddu", "lalu", "manu", "mokesh",
    "munna", "pappu", "pinku", "sonu", "tinku",
    "aditya", "ajay", "ajit", "akash", "akhil", "akshay", "alok",
    "aman", "amar", "amit", "amol", "amrit", "anand", "anant", "ananth",
    "anil", "ankit", "ankur", "ansh", "anuj", "anup", "apoorv", "arjun",
    "arpit", "arun", "arvind", "ashish", "ashok", "atharv", "atul",
    "ayush", "balaji", "balram", "bharat", "bhaskar", "bhushan",
    "bhuvan", "bipin", "birju", "brijesh", "chandan", "chandra",
    "charan", "chetan", "darshan", "deepak", "dev", "devansh", "devraj",
    "dhanesh", "dharmesh", "dhruv", "digvijay", "dinesh", "divyansh",
    "gaurav", "gautam", "girish", "gopal", "govind", "hardik", "hari",
    "harish", "harsh", "harshvardhan", "hemant", "hitesh", "ishaan",
    "jagdish", "jai", "jay", "jayant", "jayesh", "jignesh", "jitendra",
    "kailash", "kamal", "kamlesh", "kapil", "karan", "kartik",
    "keshav", "kishan", "kishor", "kishore", "krishna", "kuldeep",
    "kumar", "kunal", "lalit", "laxman", "lokesh", "madhav", "mahendra",
    "mahesh", "manas", "manav", "manish", "manoj", "mayank", "mehul",
    "milan", "mithun", "mohan", "mohit", "mridul", "mrinal", "mukesh",
    "mukul", "mukund", "naman", "naresh", "navin", "naveen", "neeraj",
    "nilesh", "niraj", "nirmal", "nitesh", "nitin", "om", "omkar",
    "pankaj", "parth", "piyush", "prabhakar", "pradeep", "prakash",
    "pramod", "pranav", "prashant", "prateek", "praveen", "pravin",
    "prem", "prince", "puneet", "rachit", "raghav", "raghu", "rahul",
    "raj", "rajan", "rajat", "rajeev", "rajendra", "rajesh", "rajiv",
    "raju", "rakesh", "ram", "raman", "ramesh", "ranbir", "ranjit",
    "rashmi", "rathi", "ratan", "ravi", "ravindra", "rishabh", "rishi",
    "ritesh", "ritik", "rohan", "rohit", "sachin", "sagar", "sahil",
    "saiteja", "sameer", "samir", "sandeep", "sanjay", "sanjeev",
    "sankalp", "santosh", "saraansh", "satish", "satya", "saurabh",
    "shahid", "shakti", "shaktiman", "shankar", "shantanu", "shashank",
    "shashi", "shiv", "shivam", "shubh", "shubham", "shyam",
    "siddharth", "sohan", "sohil", "somesh", "subhash", "sudhanshu",
    "sudhir", "sujit", "suman", "sumit", "sundar", "sunil", "surendra",
    "suresh", "surya", "swapnil", "tanmay", "tarun", "tej", "tejas",
    "tejpal", "tushar", "uday", "umesh", "upendra", "utkarsh", "uttam",
    "vaibhav", "varun", "vibhor", "vidyut", "vijay", "vikas", "vikram",
    "vimal", "vinay", "vineet", "vinod", "viraj", "virat", "vishal",
    "vishnu", "vivek", "vyom", "yash", "yashpal", "yogesh", "yogi",
    "yuvraj",
    # ── Common Muslim first names (male) ──────────────────────────────
    "aamir", "aarif", "aas", "abdul", "abrar", "adil", "adnan", "afsar",
    "ahmad", "ahmed", "ajaz", "akbar", "akhtar", "akram", "alam",
    "ameer", "amir", "anwar", "arif", "asad", "ashfaq", "asif", "atiq",
    "ayaan", "ayaz", "azhar", "aziz", "azim", "bilal", "danish",
    "ehsan", "fahad", "faisal", "faiz", "faizan", "farhan", "farid",
    "feroz", "ghulam", "habib", "haider", "hamid", "hanif", "haroon",
    "hashim", "hassan", "hussain", "ibrahim", "iftikhar", "imran",
    "inam", "irfan", "iqbal", "ishaq", "ismail", "javed", "kabir",
    "kamran", "kashif", "khalid", "khurram", "majid", "manzoor", "masood",
    "mehboob", "mohammed", "mohsin", "muneer", "munir", "nadeem", "naeem",
    "nasir", "navaid", "nawaz", "noman", "noor", "omar", "qasim",
    "raees", "rashid", "rauf", "rehan", "rehman", "riyaz", "rizwan",
    "saad", "sabir", "sadiq", "saeed", "salim", "salman", "samad",
    "shahbaz", "shahid", "shakeel", "shaukat", "sohail", "sufyan",
    "suleman", "tahir", "tariq", "umar", "usman", "wahid", "wakil",
    "waqar", "wasim", "yasir", "yousuf", "yusuf", "zafar", "zahid",
    "zaheer", "zain", "zakir", "zia", "ziauddin", "zubair",
})


_FEMALE_NAMES: frozenset[str] = frozenset({
    # ── Classic Sanskrit / Hindi ──────────────────────────────────────
    "aaradhya", "aarti", "aishwarya", "akanksha", "akshara", "alka",
    "amrita", "anamika", "anchal", "anita", "anjali", "anju", "ankita",
    "anu", "anupama", "anushka", "apoorva", "aradhana", "archana",
    "arpita", "aruna", "asha", "ashwini", "ashima", "avani", "barkha",
    "bhakti", "bhavna", "bina", "binita", "bharti", "chanda",
    "chandni", "chetna", "chhaya", "deepa", "deepali", "deepika",
    "devika", "dhriti", "diksha", "disha", "divya", "drishti", "ekta",
    "esha", "falguni", "gargi", "gauri", "geeta", "geetika",
    "geeti", "gita", "gopika", "hansa", "hema", "heena", "ila", "indira",
    "indu", "ipsita", "isha", "ishita", "jagriti", "jagrati", "jaishree",
    "janhavi", "janavi", "janki", "jayanti", "jaya", "jhanvi", "jyoti",
    "jyotsna", "kajal", "kala", "kalpana", "kamala", "kamini", "kanak",
    "kanchan", "karishma", "karuna", "kashish", "katyayani", "kavita",
    "kavya", "khushi", "kinjal", "kiran", "komal", "kriti", "kshama",
    "lakshmi", "lalita", "laxmi", "lata", "leela", "madhavi", "madhu",
    "madhulika", "madhumita", "madhuri", "mahima", "mala", "mamta",
    "manasi", "mandakini", "manju", "manjusha", "mansi", "maya",
    "meena", "meera", "megha", "menka", "mira", "mithila", "mona",
    "monika", "mukta", "mukti", "muskan", "nainika", "naina", "namita",
    "namrata", "nandini", "nayana", "neelam", "neelima", "neena",
    "neeraja", "neeta", "neeti", "nehal", "neha", "nidhi", "nikita",
    "nilima", "nipa", "niharika", "nilanjana", "nima", "nirmala",
    "nisha", "niyati", "padma", "pallavi", "palak", "parul", "payal",
    "pinky", "pooja", "poonam", "prabha", "prachi", "pragya", "prarthana",
    "pratibha", "pratima", "preeti", "preity", "priti", "priya",
    "priyanka", "pushpa", "rachna", "radha", "ragini", "rajeshwari",
    "rajni", "rakhi", "ramya", "rani", "ranjana", "rashika", "rashmi",
    "rati", "raveena", "reena", "rekha", "renu", "renuka", "reshma",
    "ritu", "rituparna", "ritushri", "rohini", "roopa", "ruchi", "rupali",
    "saachi", "saanvi", "sadhna", "sakshi", "salonee", "saloni", "samiksha",
    "sandhya", "sangeeta", "sangita", "sanjana", "sanya", "sapna",
    "sarika", "sarita", "saroj", "saumya", "savita", "seema", "shaila",
    "shaina", "shakuntala", "shalini", "shanti", "shashi", "sheela",
    "sheetal", "shilpa", "shivani", "shobha", "shobhana", "shraddha",
    "shreya", "shreyasi", "shruti", "shubhra", "shweta", "siddhi",
    "smita", "sneha", "snigdha", "sonal", "sonia", "soniya", "soumya",
    "sucharita", "sudha", "sujata", "sukanya", "sulekha", "suman",
    "sumati", "sumitra", "sunaina", "sunanda", "sundari", "sunita",
    "supriya", "surabhi", "surbhi", "sushila", "sushma", "swarna",
    "swati", "tanvi", "tanya", "tara", "tina", "trisha", "triveni",
    "tulika", "tulsi", "udita", "uma", "umrao", "upasana", "urmila",
    "urvashi", "usha", "uttara", "vaidehi", "vaishali", "vandana",
    "vanita", "varsha", "vasudha", "vasumati", "veena", "vibha", "vibhuti",
    "vidya", "vimla", "vinita", "vrinda", "yamini", "yashoda", "yasmin",
    "zeenat", "zoya",
    # ── Common Muslim first names (female) ────────────────────────────
    "aafiya", "aaliya", "aamna", "abida", "afia", "afreen", "ahla",
    "aisha", "alia", "alishba", "ameena", "ameera", "amina", "amna",
    "amreen", "anam", "asma", "ayesha", "azra", "bushra", "fareeda",
    "farah", "fariha", "farzana", "fatima", "fauzia", "firdaus", "fiza",
    "ghazala", "hafsa", "hajra", "hameeda", "haseena", "humaira",
    "iqra", "ishrat", "jameela", "jasmine", "kausar", "khadija", "lubna",
    "mahira", "mahnoor", "maliha", "marium", "maryam", "mehnaz", "mehreen",
    "munira", "nadia", "nafisa", "naheed", "najma", "nasreen", "naureen",
    "nayab", "nazia", "noorjehan", "razia", "reema", "rida", "rubina",
    "rukhsana", "saba", "sabira", "sadia", "saira", "salma", "samira",
    "sana", "saniya", "sara", "sarah", "shabana", "shabnam", "shaheen",
    "shahnaz", "shaista", "shamim", "shazia", "sumaiya", "sumayya",
    "tabassum", "tasneem", "uzma", "yasmeen", "zara", "zarina", "zenab",
    "zinat",
})


def detect_gender(full_name: str) -> str:
    """Return ``"male"``, ``"female"``, or ``"unknown"`` for an Indian name.

    Matches on the first word (whitespace-split) of the supplied name,
    lower-cased. Only common Indian first names are covered — anything
    else returns ``"unknown"`` so the caller can fall back to a neutral
    avatar.
    """
    if not full_name:
        return "unknown"
    first = full_name.strip().split()[0].lower()
    if first in _MALE_NAMES:
        return "male"
    if first in _FEMALE_NAMES:
        return "female"
    return "unknown"
