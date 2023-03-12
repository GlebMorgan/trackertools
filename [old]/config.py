from pathlib import Path
from tools import ConfigDict


PROJECT_PATH = Path(__file__).parent


CONFIG = ConfigDict(
    debug = True,
    filter_personal = True,
    scrollback = False,

    project_path = PROJECT_PATH,
    cache_path = PROJECT_PATH / '__cache__',

    backend = 'timeular',

    timeular = dict(
        key = "MTEwMTI3XzJiMzRiMzM4MDRmNzRiOTk5ODdiNWZmNjEzOTJiY2Q1",
        secret = "MDhjZDNkNTY5NjI2NGQyOTg5ZTY1YjcwMDEwNzdhMzk=",
    ),

    timecamp = dict(
        key = "68f5ea0d315e3cc33dac916fa7",
        secret = "",
    ),

    general_tasks = dict(
        Personal = None,
        Lunch = None,
        General = 'DEV3-75',
        Meeting = 'DEV3-75',
        MergeRequest = 'DEV3-75',
        Relocation = 'DEV3-75',
    ),

    client_names = dict (
        RM = 'Roseman',
        FC = 'Frotcom',
        KM = 'K-Master',
        AG = 'AlertGasoil',
        IM = 'IDEM',
        AR = 'AROBS',
    ),
)
