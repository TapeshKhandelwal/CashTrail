"""Static reference data for the demo organisation: branches, staff, bank accounts, customers."""

from dataclasses import dataclass

from apps.accounts.models import User

DEMO_PASSWORD = "Demo@12345"
EMAIL_DOMAIN = "cashtrail.example"


@dataclass(frozen=True, slots=True)
class BranchData:
    code: str
    name: str
    city: str
    address: str
    bank_name: str
    account_last4: str
    ifsc: str


@dataclass(frozen=True, slots=True)
class StaffData:
    username: str
    first_name: str
    last_name: str
    role: str
    branch_code: str = ""


BRANCHES = (
    BranchData(
        code="BLR01",
        name="Bengaluru Central",
        city="Bengaluru",
        address="3rd Floor, 41 MG Road, Ashok Nagar, Bengaluru, Karnataka 560001",
        bank_name="HDFC Bank",
        account_last4="4821",
        ifsc="HDFC0000523",
    ),
    BranchData(
        code="MUM01",
        name="Mumbai Andheri",
        city="Mumbai",
        address="Unit 512, Andheri-Kurla Road, Chakala, Andheri East, Mumbai, Maharashtra 400093",
        bank_name="ICICI Bank",
        account_last4="7305",
        ifsc="ICIC0000104",
    ),
    BranchData(
        code="DEL01",
        name="Delhi Connaught Place",
        city="New Delhi",
        address="2nd Floor, 18 Barakhamba Road, Connaught Place, New Delhi, Delhi 110001",
        bank_name="State Bank of India",
        account_last4="1946",
        ifsc="SBIN0000691",
    ),
)

COMPANY_ACCOUNT_NAME = "CashTrail Finance Pvt Ltd"
GATEWAY_ACCOUNT = {
    "bank_name": "Kotak Mahindra Bank",
    "account_name": f"{COMPANY_ACCOUNT_NAME} - Razorpay settlements",
    "account_number_last4": "6630",
    "ifsc": "KKBK0000958",
    "is_gateway": True,
}

_ADMIN, _FINANCE = User.Role.ADMIN, User.Role.FINANCE
_MANAGER, _AGENT = User.Role.BRANCH_MANAGER, User.Role.AGENT

STAFF = (
    StaffData("admin", "Arjun", "Mehta", _ADMIN),
    StaffData("finance", "Priya", "Raghavan", _FINANCE),
    StaffData("manager.blr", "Kavitha", "Rao", _MANAGER, "BLR01"),
    StaffData("agent.blr1", "Ravi", "Kumar", _AGENT, "BLR01"),
    StaffData("agent.blr2", "Manjunath", "Gowda", _AGENT, "BLR01"),
    StaffData("agent.blr3", "Deepa", "Shetty", _AGENT, "BLR01"),
    StaffData("manager.mum", "Sandeep", "Kulkarni", _MANAGER, "MUM01"),
    StaffData("agent.mum1", "Rahul", "Patil", _AGENT, "MUM01"),
    StaffData("agent.mum2", "Sneha", "Jadhav", _AGENT, "MUM01"),
    StaffData("agent.mum3", "Imran", "Shaikh", _AGENT, "MUM01"),
    StaffData("manager.del", "Neha", "Arora", _MANAGER, "DEL01"),
    StaffData("agent.del1", "Vikas", "Yadav", _AGENT, "DEL01"),
    StaffData("agent.del2", "Pooja", "Sharma", _AGENT, "DEL01"),
    StaffData("agent.del3", "Amit", "Chauhan", _AGENT, "DEL01"),
)

CUSTOMER_NAMES = {
    "BLR01": (
        "Suresh Babu",
        "Lakshmi Narayan",
        "Anil Hegde",
        "Shwetha Gowda",
        "Prakash Reddy",
        "Nandini Murthy",
        "Venkatesh Iyer",
        "Rekha Kamath",
        "Harish Shenoy",
        "Savitha Nair",
        "Kiran Bhat",
        "Girish Patil",
        "Meena Krishnan",
        "Raghavendra Rao",
        "Asha Kulkarni",
    ),
    "MUM01": (
        "Vijay Pawar",
        "Sunita More",
        "Ganesh Shinde",
        "Anjali Deshmukh",
        "Mahesh Chavan",
        "Nasreen Ansari",
        "Prashant Sawant",
        "Kavita Joshi",
        "Rajesh Gupta",
        "Swati Naik",
        "Dinesh Mhatre",
        "Rohini Gaikwad",
        "Sachin Bhosale",
        "Ayesha Qureshi",
        "Nitin Salunkhe",
    ),
    "DEL01": (
        "Rakesh Verma",
        "Sunil Bansal",
        "Manju Devi",
        "Ajay Rathi",
        "Ritu Malhotra",
        "Deepak Saini",
        "Kamlesh Kumari",
        "Harpreet Kaur",
        "Manoj Pandey",
        "Shabana Siddiqui",
        "Naveen Khurana",
        "Sarita Rawat",
        "Gurpreet Sethi",
        "Anita Bhardwaj",
        "Vinod Joshi",
    ),
}

# (locality, PIN code) pairs; addresses are composed per city in `customer_address`.
LOCALITIES = {
    "BLR01": (
        ("Jayanagar 4th Block", "560011"),
        ("Malleshwaram", "560003"),
        ("BTM Layout 2nd Stage", "560076"),
        ("Rajajinagar", "560010"),
        ("Banashankari 2nd Stage", "560070"),
        ("Yelahanka New Town", "560064"),
        ("KR Puram", "560036"),
        ("Basavanagudi", "560004"),
    ),
    "MUM01": (
        ("Andheri East", "400069"),
        ("Jogeshwari West", "400102"),
        ("Goregaon East", "400063"),
        ("Vile Parle East", "400057"),
        ("Malad West", "400064"),
        ("Kurla West", "400070"),
    ),
    "DEL01": (
        ("Lajpat Nagar II", "110024"),
        ("Karol Bagh", "110005"),
        ("Rajouri Garden", "110027"),
        ("Mayur Vihar Phase 1", "110091"),
        ("Janakpuri", "110058"),
        ("Laxmi Nagar", "110092"),
    ),
}
MUMBAI_BUILDINGS = (
    "Sai Darshan CHS",
    "Shree Ganesh Apartments",
    "Laxmi Niwas",
    "Shanti Kunj CHS",
    "Om Sai Residency",
)
DELHI_BLOCKS = "ABCDEFGHJK"


def customer_address(branch_code: str, rng) -> str:
    locality, pin = rng.choice(LOCALITIES[branch_code])
    number = rng.randint(2, 480)
    if branch_code == "BLR01":
        return f"No. {number}, {_ordinal(rng.randint(1, 14))} Main, {locality}, Bengaluru {pin}"
    if branch_code == "MUM01":
        flat = f"{rng.randint(1, 12)}0{rng.randint(1, 6)}"
        return f"Flat {flat}, {rng.choice(MUMBAI_BUILDINGS)}, {locality}, Mumbai {pin}"
    block = rng.choice(DELHI_BLOCKS)
    return f"House No. {number}, {block} Block, {locality}, New Delhi {pin}"


def mobile_number(rng) -> str:
    return f"{rng.choice('6789')}{rng.randint(0, 999_999_999):09d}"


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
