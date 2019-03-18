from math import *
from numpy import mean
from BEEt_config import *


steps_per_mm = mean([config['steps_per_mm_x'], config['steps_per_mm_y'], config['steps_per_mm_z'], config['steps_per_mm_e0']])

lst=[]




global t_stepper
t_stepper = 0.0

def step_motors(current_block):
    global t_stepper
    
    trapezoid_adjusted_rate = current_block.initial_rate
    step_events_completed = 0


    delta_t_acceleration = 0.0
    delta_t_deceleration = 0.0
    t_block = 0.0

    for j in range(round(current_block.step_event_count)):
        ## check acceleration:
        if (step_events_completed < current_block.accelerate_until):
            ##if ( accel_flag ):
            trapezoid_adjusted_rate += current_block.rate_delta
            if (trapezoid_adjusted_rate >= current_block.nominal_rate):
                trapezoid_adjusted_rate = current_block.nominal_rate
            t_cur_step = set_step_events_per_minute(trapezoid_adjusted_rate)
##            accel_flag = 0


        ## check deceleration:
        elif (step_events_completed >= current_block.decelerate_after):
##            if (step_events_completed == current_block.decelerate_after):
##                t_cur_step = 0.0
##                    trapezoid_tick_cycle_counter = CYCLES_PER_ACCELERATION_TICK/2
##            else:
            ##if ( accel_flag ):
            trapezoid_adjusted_rate = max([trapezoid_adjusted_rate-current_block.rate_delta, 0.0])
            if (trapezoid_adjusted_rate < current_block.final_rate):
                trapezoid_adjusted_rate = current_block.final_rate
            t_cur_step = set_step_events_per_minute(trapezoid_adjusted_rate)
##            accel_flag = 0
                

        ## plateau:
        else:
            ##if (trapezoid_adjusted_rate != current_block.nominal_rate):    ## make sure we cruise exactly at the nominal rate.
            ##    trapezoid_adjusted_rate = current_block.nominal_rate
                ##t_cur_step = set_step_events_per_minute(trapezoid_adjusted_rate)
            t_cur_step = 0.0
                
        
##            acceleration_tmp = ACCELERATION_const
##            t_cur_step = ((-trapezoid_adjusted_rate /60.0 + sqrt((trapezoid_adjusted_rate /60.0)**2-4.0*0.5*acceleration_tmp*(-current_block.delta_mm)))/(acceleration_tmp))            ##fórmula resolvente para o t, com movimento uniformemente variado
        t_block += t_cur_step

        step_events_completed = j+1
        
        
##        print(t_block/100.0)
##        input()
    t_stepper += t_block

##    print("\t%.3fm" %(t_stepper/60.0))
    return t_stepper      ##retorna o tempo total gasto em acelerações e desacelerações (o tempo de plateau não está incluído).

'''    f = pylab.plt.figure()
    pylab.plot(lst)
    f.show()
    input()
'''




def set_step_events_per_minute(steps_per_minute):
    lst.append(steps_per_minute)
    if steps_per_minute!=0:
##        var = (((TICKS_PER_MICROSECOND*1000.0)*1000.0)/steps_per_minute*60.0)
##        t = f(var, ...)
        f = 1.00
        t = f*1.0/steps_per_minute*60.0
    else:
        t = 0.0
    return t




'''
init_counter = -(current_block.step_event_count >> 1)
counter_x = init_counter
counter_y = init_counter
counter_z = init_counter
counter_e = init_counter
step_events_completed = 0

direction_bits = current_block.direction_bits
step_bits_xyz = 0
step_bits_e = 0


if (current_block.action_type == AT_MOVE):
    ##execute step displacement profile by bresenham line algorithm
    step_bits_xyz = 0
    step_bits_e = 0

    counter_x += current_block.steps_x
    if (counter_x > 0):
        step_bits_xyz |= (1<<X_STEP_BIT)
        counter_x -= current_block.step_event_count
    counter_y += current_block.steps_y
    if (counter_y > 0):
        step_bits_xyz |= (1<<Y_STEP_BIT)
        counter_y -= current_block.step_event_count
    counter_z += current_block.steps_z
    if (counter_z > 0):
        step_bits_xyz |= (1<<Z_STEP_BIT)
        counter_z -= current_block.step_event_count

    counter_e += current_block.steps_e
    if (counter_e > 0):
        step_bits_e |= (1<<E_STEP_BIT)
        counter_e -= current_block.step_event_count


    step_events_completed+=1            ##iterate step events
            ...
'''
