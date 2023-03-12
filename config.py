import sys

from pathlib import PurePath

from tools import ConfigDict, noop


PROJECT_PATH = PurePath(__file__).parent


# fmt: off
CONFIG = ConfigDict(
    debug = True,
    filter_personal = True,
    scrollback = False,

    project_path = PROJECT_PATH,
    cache_path = PROJECT_PATH / '__cache__',

    backend = 'timecamp',

    api = dict(
        timeular = dict(
            key = "MTEwMTI3XzJiMzRiMzM4MDRmNzRiOTk5ODdiNWZmNjEzOTJiY2Q1",
            secret = "MDhjZDNkNTY5NjI2NGQyOTg5ZTY1YjcwMDEwNzdhMzk=",
        ),
        timecamp = dict(
            key = "68f5ea0d315e3cc33dac916fa7",
        ),
    ),

    general_tasks = {
        'Personal':               None,
        'Lunch':                  None,
        'Time-off':               None,
        'Teltonika':             'DEV3-75',
        'General':               'DEV3-75',
        'Competency Evaluation': 'DEV3-75',
        'Consult':               'DEV3-75',
        'Email Management':      'DEV3-75',
        'Health Diagram':        'DEV3-75',
        'Internal Trainings':    'DEV3-75',
        'Jira Management':       'DEV3-75',
        'RND Management':        'DEV3-75',
        'SonarQube Fixes':       'DEV3-75',
        'Tasks Estimation':      'DEV3-75',
        'Meeting':               'DEV3-75',
        'SonarQube Review':      'DEV3-75',
        'Sprint Estimation':     'DEV3-75',
        'Sprint Planning':       'DEV3-75',
        'Sprint Retro':          'DEV3-75',
        'Sprint Review':         'DEV3-75',
        'StandUp':               'DEV3-75',
        'Merge Request':         'DEV3-75',
        'Configurator':          'DEV3-75',
        'Configuration':         'DEV3-75',
        'Localization':          'DEV3-75',
        'FMB6':                  'DEV3-75',
        'CommonIDs':             'DEV3-75',
        'SpecProjects':          'DEV3-75',
        'ServerMain':            'DEV3-75',
        'Relocation':            'DEV3-75',
    },

    specs = dict(
        RM = 'Roseman',
        FC = 'Frotcom',
        KM = 'KMaster',
        AG = 'AlertGasoil',
        IM = 'IDEM',
        AR = 'AROBS',
        ED = 'EcoDriving',
        UT = 'UnitTests',
        TR = 'Tetra',
    ),
)

trace = print if CONFIG.debug is True or '-d' in sys.argv else noop
