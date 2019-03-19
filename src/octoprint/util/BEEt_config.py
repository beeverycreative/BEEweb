############### variáveis comuns para o planner, para o stepper e /ou para o main
## definição de constantes globais:
global ACCELERATION_const
global X_AXIS, Y_AXIS, Z_AXIS, E_AXIS
global config
global ACCELERATION_TICKS_PER_SECOND
global JUNCTION_DEVIATION
global MINIMUM_PLANNER_SPEED
global MAX_FEED_X, MAX_FEED_Y, MAX_FEED_Z, MAX_FEED_E0

ACCELERATION_const=500.0                    ## propriedades da beethefirst definidas tal como no planner.h
(X_AXIS, Y_AXIS, Z_AXIS, E_AXIS) = range(4)
config={}
config['steps_per_mm_x']=78.778             ## p/ a beethefirst (def. no planner.h)
config['steps_per_mm_y']=78.778             ## p/ a beethefirst
config['steps_per_mm_z']=112.540            ## p/ a beethefirst
config['steps_per_mm_e0']=441.390           ## p/ a beethefirst
#config['steps_per_mm_x']=...
#config['steps_per_mm_y']=...
#config['steps_per_mm_z']=...
ACCELERATION_TICKS_PER_SECOND=1000.0
JUNCTION_DEVIATION=0.05         ## /?\
MINIMUM_PLANNER_SPEED=0.0
MAX_FEED_X=60000.0
MAX_FEED_Y=60000.0
MAX_FEED_Z=60000.0
MAX_FEED_E0=60000.0
MAX_SIZE_BUFFER = 3                         ## /!\ atenção
                                            ## -> esta variável vai determinar o tamanho do buffer, para imitar o firmware


## definição de variáveis globais:
global verbose
global t_total
global number_of_warnings
verbose=0                                   ## esta variável vai definir a presença /ausência de outputs adicionais
t_total=0.0
number_of_warnings=0




############### variáveis para o stepper
global MINIMUM_STEPS_PER_MINUTE
global F_CPU
global TICKS_PER_MICROSECOND
MINIMUM_STEPS_PER_MINUTE = 1200
F_CPU = 100000000.0       ##/* 100MHz */      -> definido no ./beethefirst/machine.h
TICKS_PER_MICROSECOND = (F_CPU/1000000.0)
