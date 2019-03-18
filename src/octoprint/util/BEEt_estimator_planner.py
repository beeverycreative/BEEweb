from math import *
from BEEt_config import *




class BLOCK():
    def __init__(self, gcode_feedrate, gcode_mm):
        self.nominal_speed=gcode_feedrate               ## the nominal speed for this block in mm/min
        self.entry_speed=0.0                            ## entry speed at previous-current junction in mm/min
        self.max_entry_speed=0.0                        ## maximum allowable junction entry speed in mm/min
        self.millimeters=gcode_mm                       ## the total travel of this block in mm
        self.recalculate_flag=True                      ## planner flag to recalculate trapezoids on entry junction
        self.nominal_length_flag=False                  ## planner flag for nominal speed always reached
        self.initial_rate=0.0                           ## the jerk-adjusted step rate at start of block  
        self.final_rate=0.0                             ## the minimal rate at exit
        self.delta_mm_x=0.0
        self.delta_mm_y=0.0
        self.delta_mm_z=0.0
        self.accelerate_until=0.0
        self.decelerate_after=0.0
        self.accelerate_until_mm=0.0
        self.decelerate_after_mm=0.0
        self.delta_mm=0.0


    def __str__(self):
        my_str=('\nBLOCK:')
        my_str+=('\n\tnominal_speed:')
        my_str+=('\t'+str(self.nominal_speed))
        my_str+=('\n\tentry_speed:')
        my_str+=('\t'+str(self.entry_speed))
##      my_str+=('\n\tmax_entry_speed:')
##      my_str+=('\t'+str(self.max_entry_speed))
        my_str+=('\n\tmillimeters:')
        my_str+=('\t'+str(self.millimeters))
##      my_str+=('\n\trecalculate_flag:')
##      my_str+=('\t'+str(self.recalculate_flag))
##      my_str+=('\n\tnominal_length_flag:')
##      my_str+=('\t'+str(self.nominal_length_flag))
##      my_str+=('\n\tinitial_rate:')
##      my_str+=('\t'+str(self.initial_rate))
##      my_str+=('\n\tfinal_rate:')
##      my_str+=('\t'+str(self.final_rate))
        my_str+=('\n\taccelerate_until_mm:')
        my_str+=('\t'+str(self.accelerate_until_mm))
        my_str+=('\n\tdecelerate_after_mm:')
        my_str+=('\t'+str(self.decelerate_after_mm))
        my_str+=('\n\tdelta_mm:')
        my_str+=('\t'+str(self.delta_mm))
        
        return my_str




def init_instructions(blocks_full_list, list_G0sG1s):
    for i in range(len(list_G0sG1s)):
        element=list_G0sG1s[i]
        (x_point, y_point, z_point, feed_rate, e_length, block_millimeters) = element
        if i<(len(list_G0sG1s)-1):
            element_next = list_G0sG1s[i+1]
            (x_point_next, y_point_next, z_point_next, f, e_length_next, block_millimeters) = element_next
        if f==0:
            ##print('e only!')
            pass
        block=BLOCK(f, block_millimeters)           ## um bloco corresponde a um segmento, aqui são inicilizadas apenas a feed_rate e a distância em mm
                                                    ## as restantes propriedades são definidas entretanto
        ## number of steps for each axis
        x=x_point
        y=y_point
        z=x_point

        if i<(len(list_G0sG1s)-1):
            blocks_full_list.append(block)                  ## adiciona o bloco à lista
        
##            e=0.0   ## <--  /!\ to be changed latter!
            block.delta_mm_x = (x_point_next-x_point)        ## inicializa a distância percorrida segundo cada direcção: x, y, e z.
            block.delta_mm_y = (y_point_next-y_point)
            block.delta_mm_z = (z_point_next-z_point)
            block.delta_mm_e = abs(e_length_next-e_length)

            block.delta_mm = max((abs(block.delta_mm_x), abs(block.delta_mm_y), abs(block.delta_mm_z)))
            block.delta_mm = max((block.delta_mm, block.delta_mm_e))
            
            
            if verbose:
                print("block.delta_mm:")                    ## o código está a funcionar bem para:
                                                            ##      i) block.delta_mm=block_millimeters (ou seja para uma direcção, i.e. os mm percorridos na direção com maior distância são iguais aos mm percorridos ao todo)
                                                            ##      ii) para config['steps_per_mm_x']>>0, config['steps_per_mm_y']>>0, e config['steps_per_mm_z']>>0 (i.e. casos em que arredondamentos devido aos steps_per_mm não afectam o resultado)
                print(block.delta_mm)
            block.step_event_count = max((abs(block.delta_mm_x)*config['steps_per_mm_x'], abs(block.delta_mm_y)*config['steps_per_mm_y'], abs(block.delta_mm_z)*config['steps_per_mm_z']))     ## o nº de eventos de cada bloco corresponde ao nº de eventos da direcção com maior quantidade de eventos
    
                
            if block.millimeters == 0:
                block.e_only = True
                block.millimeters = abs(block.delta_mm_e)
            else:
                block.e_only = False
                
    
            if (block_millimeters==0) or (f==0):
                block.nominal_rate = 0.0
                block.rate_delta = 0.0
            else:
                microseconds = round((block_millimeters/f*60.0)*1000000.0)          ## factor para usar em cálculos posteriores, à semelhança do planner.c
                
                multiplier = 60.0*1000000.0/microseconds                            ## à semelhança do planner.c
                speed_x = block.delta_mm_x * multiplier
                speed_y = block.delta_mm_y * multiplier
                speed_z = block.delta_mm_z * multiplier
                speed_e = block.delta_mm_e * multiplier
                block.speed_e = speed_e
                '''speed_e = delta_mm[E_AXIS] * multiplier
'''
                ## limit speed per axis
                speed_factor = 1            ##factor <=1 do decrease speed
                if (fabs(speed_x) > MAX_FEED_X):
                    speed_factor = MAX_FEED_X / fabs(speed_x)
                if (fabs(speed_y) > MAX_FEED_Y):
                    tmp_speed_factor = MAX_FEED_Y / fabs(speed_y)
                    if(speed_factor > tmp_speed_factor):
                        speed_factor = tmp_speed_factor
                if (fabs(speed_z) > MAX_FEED_Z):
                    tmp_speed_factor = MAX_FEED_Z / fabs(speed_z)
                    if(speed_factor > tmp_speed_factor):
                        speed_factor = tmp_speed_factor
                if(fabs(speed_e) > MAX_FEED_E0):
                    tmp_speed_factor = MAX_FEED_E0 / fabs(speed_e)
                    if(speed_factor > tmp_speed_factor):
                        speed_factor = tmp_speed_factor

                multiplier = multiplier * speed_factor
                
                block.nominal_speed = block_millimeters * multiplier                    ## mm per min -> from planner.c
##                block.nominal_speed = f                                                 ## ...        -> BEEestimator_t
                block.nominal_rate = ceil(block.step_event_count * multiplier);         ## steps per minute
                block.rate_delta = ceil( block.step_event_count/block_millimeters * ACCELERATION_const*60.0 / ACCELERATION_TICKS_PER_SECOND )     ## units: (step/min/acceleration_tick)
                
        ## compute vmax_junction:
        vmax_junction = MINIMUM_PLANNER_SPEED

        if block_millimeters:
            unit_vec_xx = block.delta_mm_x/block_millimeters
            unit_vec_yy = block.delta_mm_y/block_millimeters
            unit_vec_zz = block.delta_mm_z/block_millimeters
        else:
            unit_vec_xx = 0.0
            unit_vec_yy = 0.0
            unit_vec_zz = 0.0
            

        if i!=0:        ## salta o 1º bloco
                        ## cálculos análogos ao que está no planner.c, para obter max_junction
            cos_theta = - previous_unit_vec_xx * unit_vec_xx - previous_unit_vec_yy * unit_vec_yy - previous_unit_vec_zz * unit_vec_zz

            ## for ~0º acute junction...
            if (cos_theta < 0.95):
                vmax_junction = min([previous_nominal_speed, block.nominal_speed])
                if verbose:
                    print('vmax_junction: '+str(vmax_junction))
                    print('vmax--^\n\n')
                ## for ~180º...
                if (cos_theta > -0.95):
                    sin_theta_d2 = sqrt(0.5*(1.0-cos_theta))
                    vmax_junction = min(vmax_junction, sqrt(ACCELERATION_const*60.0*60.0 * JUNCTION_DEVIATION * sin_theta_d2/(1.0-sin_theta_d2)) )
                    
        block.max_entry_speed = vmax_junction
        if verbose:
            print("i -- IMPORTANT: "+str(i))
            print('vmax_junction: '+str(vmax_junction))
            print('depois: vmax--^\n')
        
        ## initialize block entry speed:
        v_allowable = max_allowable_speed(-ACCELERATION_const,MINIMUM_PLANNER_SPEED,block_millimeters)
        if verbose:
            print("v_allowable(): //!\\\\\t\t"+str(v_allowable))
        block.entry_speed = min(vmax_junction, v_allowable)
        
        block.entry_speed = MINIMUM_PLANNER_SPEED    
        

        if (block.nominal_speed <= v_allowable):
            block.nominal_length_flag = True
        else:
            block.nominal_length_flag = False

        previous_unit_vec_yy = unit_vec_yy
        previous_unit_vec_xx = unit_vec_xx
        previous_unit_vec_zz = unit_vec_zz

        previous_nominal_speed = block.nominal_speed
        
        


def planner_reverse_pass_kernel(block_t_prev, block_t_current, next_entry_speed):
    if (block_t_current.entry_speed != block_t_current.max_entry_speed):
        if verbose:
            print(block_t_current.nominal_length_flag)
            print(block_t_current.max_entry_speed)
            print(next_entry_speed)
        if ((not block_t_current.nominal_length_flag) and (block_t_current.max_entry_speed > next_entry_speed)):
            block_t_current.entry_speed = min( block_t_current.max_entry_speed, max_allowable_speed(-ACCELERATION_const, next_entry_speed, block_t_current.millimeters))
        else:
            block_t_current.entry_speed = block_t_current.max_entry_speed

        block_t_current.recalculate_flag = True
        return True

    return False




def planner_reverse_pass(block_buffer):
    if verbose:
        print('ON planner_reverse_pass()...')
    replan_prev = False
    block_buffer_head = 0
    block_index = len(block_buffer)-1

    next = 'NULL'
    cur = block_buffer[block_index]
    prev = block_buffer[block_index-1]

    while (block_index != block_buffer_head):
        if verbose:
            print("block_index: "+str(block_index))
        if (replan_prev and cur):
            cur.recalculate_flag = True

        ## skip buffer head/first block to prevent over-writing the initial entry speed.
        if ( (cur != 'NULL') and (next != 'NULL') ):
            replan_prev = planner_reverse_pass_kernel (prev, cur, next.entry_speed)
        else:
            replan_prev = planner_reverse_pass_kernel (prev, cur, 0.0)

        ## move to next block
        block_index-=1
        next = cur
        cur = prev
        try:
            prev = block_buffer[block_index]
        except:
            prev = 'NULL'

    if (replan_prev and cur!='NULL'):
        cur.recalculate_flag = True




def planner_forward_pass_kernel(block_t_previous, block_t_current):
    if (not block_t_previous.nominal_length_flag):
        if (block_t_previous.entry_speed < block_t_current.entry_speed):
            entry_speed = min( block_t_current.entry_speed, max_allowable_speed(-ACCELERATION_const,block_t_previous.entry_speed,block_t_previous.millimeters) )
            
            ## check for junction speed change
            if (block_t_current.entry_speed != entry_speed):
                block_t_current.entry_speed = entry_speed
                block_t_current.recalculate_flag = True




def planner_forward_pass(block_buffer):
    if verbose:
        print('ON planner_forward_pass()...')
    block_index = 0;

    next = 'NULL'
    cur = 'NULL'
    prev = 'NULL'

    while (block_index != len(block_buffer)):
        if verbose:
            print("block_index: "+str(block_index))
        prev = cur
        cur = next
        next = block_buffer[block_index];

        if ( (cur != 'NULL') and (prev != 'NULL') ):
            planner_forward_pass_kernel (prev, cur)

        block_index+=1;

    if (cur != 'NULL'):
        planner_forward_pass_kernel(cur, next);




#/*                            PLANNER SPEED DEFINITION                                              
#                                     +--------+   <- current->nominal_speed
#                                    /          \                                
#         current->entry_speed ->   +            \                               
#                                   |             + <- next->entry_speed
#                                   +-------------+                              
#                                       time -->                                 
# */
#// recalculates the trapezoid speed profiles for flagged blocks in the plan...
def planner_recalculate_trapezoids(block_buffer):
    block_index = 0
    block_t_current = block_buffer[block_index]
    block_t_next = 'NULL'

    while_lock = 0
    block_buffer_tail = len(block_buffer)


    while (block_index != block_buffer_tail):
        block_t_current = block_t_next
        block_t_next = block_buffer[block_index]

        if (block_t_current != 'NULL'):
            ## recalculate if block_t_current block entry or exit junction speed has changed
            if (block_t_current.recalculate_flag):
                ## NOTE: entry and exit factors always > 0 by all previous logic operations.
                if block_t_current.nominal_speed:
                    calculate_trapezoid_for_block(block_t_current, block_t_current.entry_speed/block_t_current.nominal_speed, block_t_next.entry_speed/block_t_current.nominal_speed)
        block_index+=1

    ## last/newest block in buffer -- exit speed is set with MINIMUM_PLANNER_SPEED, always recalculated.
    ## ... :  removed unneed code /?\




def calculate_trapezoid_for_block(block, entry_factor, exit_factor):
    if block.millimeters:
        block.initial_rate = ceil(block.nominal_rate*entry_factor)                       ## (step/min)
        block.final_rate = ceil(block.nominal_rate*exit_factor)                          ## (step/min)
        acceleration_per_minute = block.rate_delta*ACCELERATION_TICKS_PER_SECOND*60.0    ## (step/min^2)
        accelerate_steps = ceil(estimate_acceleration_distance(block.initial_rate, block.nominal_rate, acceleration_per_minute))
        #print("...")
        decelerate_steps = floor(estimate_acceleration_distance(block.nominal_rate, block.final_rate, -acceleration_per_minute))

        ## calculate the size of plateau of nominal rate. 
        plateau_steps = block.step_event_count-accelerate_steps-decelerate_steps

        '''## /!\
        print(block.millimeters)
        print(block.step_event_count)
'''

        ## is the plateau of nominal rate smaller than nothing?
        ## if yes, that means no cruising, and we will have to use intersection_distance() to calculate when to abort acceleration and start braking in order to reach the final_rate exactly at the end of this block.
        if (plateau_steps < 0):
            accelerate_steps = ceil(intersection_distance(block.initial_rate, block.final_rate, acceleration_per_minute, block.step_event_count))
            #print(accelerate_steps)
            accelerate_steps = max(accelerate_steps,0)       ## check limits due to numerical round-off
            #print(accelerate_steps)
            #print(block.step_event_count)

            accelerate_steps = min(accelerate_steps,block.step_event_count)
            #print(accelerate_steps)
            plateau_steps = 0

        if block.step_event_count!=0:
            block.accelerate_until = accelerate_steps
            block.decelerate_after = (accelerate_steps+plateau_steps)
            block.accelerate_until_mm = block.accelerate_until*(block.delta_mm/block.step_event_count)
            block.decelerate_after_mm = block.decelerate_after*(block.delta_mm/block.step_event_count)
        else:
            pass
        block.recalculate_flag = False
        
        
        
        
## calculates the maximum allowable speed - planner.c
def max_allowable_speed(acceleration, target_velocity, distance):
    result = sqrt(target_velocity*target_velocity-2.0*acceleration*60.0*60.0*distance)
    if verbose:
        print("ARGs:")
        print(acceleration)
        print(target_velocity)
        print(distance)
        print("RESULT: "+str(result))
    return result




## calculates the distance it takes to accelerate from initial_rate to target_rate using the given acceleration - planner.c
def estimate_acceleration_distance(initial_rate, target_rate, acceleration):
    try:
        if verbose:
            print(target_rate)
            print(initial_rate)
        return (target_rate*target_rate-initial_rate*initial_rate)/(2.0*acceleration)
    except:     ##catch division by 0... tmp.
        return 0




## this function gives the point at which we must start braking in the cases where the tarpezoid has no plateaun (i.e. never reaches maximum speed) - planner.c
def intersection_distance(initial_rate, final_rate, acceleration, distance):
  return 0.5*distance+(-initial_rate*initial_rate+final_rate*final_rate)/(4.0*acceleration)
