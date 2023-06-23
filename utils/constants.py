from typing import Dict, Set

MAIN_GUILD_ID: int = 716445624517656727
VERIFICATION_GUILD_ID: int = 734527161289015337
ADMIN_ROLE_ID: int = 716713238955556965
STAFF_ROLES: Set[int] = {
    716713561233031239,  # Staff
    716713266683969626,  # Senior Administrator
    ADMIN_ROLE_ID,  # Administrator
    716713498360545352,  # Senior Website Moderator
    716713293330514041,  # Website Moderator
}
CERTIFIED_ROLES: Dict[str, int] = {
    "bot": 716684142766456832,
    "developer": 716724317207003206,
}
