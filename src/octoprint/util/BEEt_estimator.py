#!/usr/bin/env python3.6
# -*- coding: utf-8 -*-

############ programa auxiliar									  ############
############	com estimativa do tempo de impressão de peças em 3d ############


############ tarefas do programa:								   ############
## ler um ficheiro *.gcode;
## interpretar cada linha com G0 e G1;
## devolve o resultado com o tempo previsto.
##
############														############


from math import *
from numpy import array, mean, linalg as LA
try:
	import pylab
except:
	print("warning: no module named pylab...")
import sys
import argparse


from BEEt_estimator_planner import *
from BEEt_estimator_stepper import *
from BEEt_buffer import *


def main_beeestimator_test():
	print "main_beeestimator_test()"


def main_beeestimator(in_gcode_beesoft="none"):
#   print("the name of the script: "+sys.argv[0])
#   print("number of arguments: "+str(len(sys.argv)))
#   print("the arguments are: ")
#   for arg in sys.argv:
#	   print("argument: "+arg)
	verbose_main=0

	if in_gcode_beesoft=="none":		##se este é o ficheiro principal, então a função main() vai usar o gcode definido na linha de comandos:
		## definição do formato de input na linha de comandos
		parser = argparse.ArgumentParser(prog='./BEEestimator_t', description='*.GCODE time estimator - p/ BEE (python3.6)')
		parser.add_argument('-i', '--input', type=str, default='', help="path of the input gcode file.", required=0)		## este argumento, que é a localizaçãpo do ficheiro *.gcode /*.gco é obrigatório
	##	parser.add_argument('-p', '--precision', type=str, default='H', help="precision options: L: low; M: medium; H: high.")
		parser.add_argument('-f', '--force', type=str, default='false', help="force options: 0/false - the program stops when it reaches a unexpected input (the default); 1/true - the program tries to continue when it finds a unexpected input.")											## há duas opções ao receber input inesperado: interromper ou tentar presseguir...
																															## o utilizador escolhe o tipo de acções com a opção --force
		parser.add_argument('-g', '--graphs', type=str, default='false', help="graphs options: 0/false - the program does not plot the graphs; 1/true - the program plots the graphs.")																										   ## de acordo com o valor desta variável, a função de fazer plots será ou não será chamada.


		args = parser.parse_args()
	##  print(vars(args))
		
		vars_dictionary=vars(args)
	##	in_precision=vars_dictionary['precision'].lower()
		in_gcode=vars_dictionary['input']
		in_force=vars_dictionary['force']
		if (in_force=='1') or (in_force.lower()=='true'):	   ## se a opção da variável de input force for 1, true, TRUE, ..., então fica definida como 1
			in_force=1
		else:												   ## caso contrário, fica 0.
			in_force=0
		in_graphs=vars_dictionary['graphs']
		if (in_graphs=='1') or (in_graphs.lower()=='true'):	 ## se a opção da variável de input graphs for 1, true, TRUE, ..., então fica definida como 1
			in_graphs=1
		else:												   ## caso contrário, fica 0.
			in_graphs=0


		if not in_gcode:
			print('--> the input was empty.\n\n')			   ## detecta se há ou não nome de ficheiro de input
			parser.print_help()
			exit()
	else:				## caso contrário, se este é um subscript de um conjunto de ficheiros maior (como por exemplo na integração com o beesoft), então vai usar o a variável: "in_gcode_beesoft".
		in_gcode=in_gcode_beesoft
		in_force=1
		

	if verbose or verbose_main:
		print ('- read_GCODE()')				   ## chama a função que vai ler e fazer o parsing do ficheiro de input
##  fname='./input/BEE_122019_13-54-42__tmp-scn.gco'
	list_G0sG1s = read_GCODE(in_gcode, in_force)


	'''
#   opt=input("\tL: low precision;\n\tM: medium precision;\n\tH: high precision (default).\ninsert opt.: ").lower();
#   if (opt!="l") and (opt!="m"):
#	   opt="h"
	opt=in_precision.lower()

	if (opt=='low') or (opt=='medium') or (opt=='high'):
		opt=opt[0]
		
	if (opt[0]=='l') or (opt[0]=='m') or (opt[0]=='h'):
		##opts.: L, M, and H
		f_estimator(list_G0sG1s, opt)
	else:
		number_of_warnings+=1
		print('WARNING: invalid input option for precision.')
		print('>>> seting up the precision to default value: "H".')
'''


	''' MAIN ALGORITHM:
		1. go over every block in reverse order and calculate a junction speed reduction (i.e. block_t.entry_speed) so that:
			a. the junction speed is equal to or less than the maximum junction speed limit;
			b. no speed reduction within one block requires faster deceleration than the one, true constant acceleration.
		2. go over every block in chronological order so that:
			a. no speed increase within one block requires faster acceleration than the one, true constant acceleration.
		3. recalculate trapezoids for all blocks using the recently updated junction speeds.
'''


	if verbose or verbose_main:
		print ('- init_instructions()')		## depois de ter lido o ficheiro vai inserir as situações num buffer
																	## e tembém vai inicializar algumas propriedades
																	## cada bloco corresponde a um segmento: tem xf, yf, e zf, feed_rate, e millimeters.
	blocks_full_list = []
	init_instructions(blocks_full_list, list_G0sG1s)


	global t_total, t_1st, t_2nd, t_3rd, t_e0
	t_total = 0.0
	t_1st = 0.0
	t_2nd = 0.0
	t_3rd = 0.0
	t_e0 = 0.0
	
	global speed_t, acceleration_t, t
	speed_t=[]
	acceleration_t=[]
	t=[]
	
	the_buffer = RING_BUFFER(MAX_SIZE_BUFFER)
	
	for i in range(0, MAX_SIZE_BUFFER):				 ##enche o buffer com os primeiros elementos
		the_buffer.receive_move(blocks_full_list[i])
	
	for i in range(MAX_SIZE_BUFFER, len(blocks_full_list)-1+MAX_SIZE_BUFFER):	   ##percorre o estado do buffer tendo um nº total de iterações igual a length de blocks_full_list.
		if i<=len(blocks_full_list)-1:
			the_buffer.receive_move(blocks_full_list[i])					## em geral, quando recebe um elemento guarda-o e remove o elemnto que está a mais;
		else:
			the_buffer.pop()												## nas últimas passagens pelo buffer vai removendo elementos, mas já não há nenhum para adicionar.
		if verbose or verbose_main:
			print('- planner_reverse_pass()')							   ## esta função vai correr o buffer de trás p/ a frente, para actualizar as variáveis entry_speed de cada bloco
		planner_reverse_pass(the_buffer)
		
		if verbose or verbose_main:
			print('- planner_forward_pass()')							   ## esta função vai correr o buffer da frente p/ trás, para actualizar as variáveis entry_speed de cada bloco
		planner_forward_pass(the_buffer)
		
		if verbose or verbose_main:
			print('- planner_recalculate_trapezoids()')					 ## esta função vai calcular as distâncias de aceleração, plateau e desaceleração p/ cada bloco, de acodo com os valores previamente computados
		planner_recalculate_trapezoids(the_buffer)

	
	##	if verbose:
	##		print('- print_actions()')
	##		print_actions(list_G0sG1s, ... )
	
		if verbose or verbose_main:
			print('- check_instructions()')

			
		(speed_t, acceleration_t, t) = check_instructions(the_buffer[0])		## esta função vai avaliar os resultados das velocidades de entrada, e de saída, e as distâncias de aceleração, plateau e desaceleração - verifica se está tudo consistente, ou seja v_f [a velociade de saída, que é igual à velocidade de entrada do bloco seguinte)], tem que ser igual à v_f(v_i, delta_t_i, a_const) [a velocidade computada de acordo com as propriedades todas do bloco.]
	
		'''if in_graphs:
			if verbose or verbose_main:
				print('- plot_graphs()')
			plot_graphs(speed_t, acceleration_t, t)
	'''

		if verbose or verbose_main:
			print('- step_motors()')								## obtem-se a soma dos tempos de aceleração e de desaceleração, calculados de acordo com os step motors
		##t_stepper_1st_and_3rd = step_motors(the_buffer[0])		## esta função é a que vai chamar os step motors
																	## - está comentada p/ o resultado ser mais rápido, e também porque afinal não é necessário.
	
	
	t_tupple = (t_1st/60.0, t_2nd/60.0, t_3rd/60.0, t_e0/60.0)	  ##guarda as somas parciais dos tempos: o tempo gasto no total com todos os pedaços de aceleração, plateau, desaceleração, e movimentação de e0
	## print("\t"+str(t_tupple))
	[t_acceleration, t_plateau, t_deceleration, t_extrusion0] = t_tupple


	if verbose or verbose_main:
		print('- print_time()')
##	print_time(t_total)										   ## tempo de acordo com o planner
##	t_tupple = ...												##guarda as somas parciais dos tempos: o tempo gasto no total com todos os pedaços de aceleração, plateau, desaceleração, e movimentação de e0
##	print("\t"+str(t_tupple))
	t_planner= sum(t_tupple)*60.0														   ## tempo de acordo com o planner
	##t_planner_and_stepper = t_stepper_1st_and_3rd+t_plateau*60.0+t_extrusion0*60.0		  ## tempo de acordo com o planner e o stepper
	print_time(t_planner)
##	print_time(t_planner_and_stepper)
##	print_time(mean([t_planner, .... ]))
		
	return t_planner




def read_GCODE(fname, in_force):
	global number_of_warnings
	
	##fname_default='./input/HBP_ls-mof_-_3d_v2018-07-10.gcode'
	##fname_default='./input/HBP_3d_king_-_1x.gcode'
	##fname_default='/home/silvia/desktop/my_docs/BEE/desafio/beeverycreative_challenge/cilindro_med_20.gco'
	##fname_default='/home/silvia/desktop/my_docs/BEE/desafio/beeverycreative_challenge/cubo_med_20.gco'

#   fname=input('insira o nome do ficheiro gcode para analisar [default: '+fname_default+']: ');
#   if not fname:
#	   fname=fname_default
##  fname=...
	try:
		f=open(fname, 'r')
	except IOError as e:
		import errno
		if e.errno==errno.ENOENT:
			print('ERROR: no such file or directory: "'+fname+'".')
		else:
			print(e)
		exit()
	
	
	x_point=0.00		##inicializar as coordenadas: (x, y, z)
	y_point=0.00
	z_point=0.00
	x_point_prev=0.00
	y_point_prev=0.00
	z_point_prev=0.00
	e_length=0.00

	time_mins=0.00				  ##inicializar a variável que vai acumulando o tempo da estimativa: para as opções "lower", ou "medium";
	time_mins_trapezoidal=0.00	  ##para a opção "higher".


	lines = f.readlines()		   ##lê as linhas todas
	index=0
	list_G0sG1s=[]
	list_G0sG1s.append((0, 0, 0, 0, 0, 0))
	index_G0G1=1
	cur_l=lines[index]
	distance=0

	while cur_l!='eof.':
		if ';' in cur_l:			##se atingir um comentário, remove-o para não o interpretar
			cur_l_command=cur_l[0:cur_l.index(';')]
		else:
			cur_l_command=cur_l
		the_list=cur_l_command.split()	  ##transforma a string da linha numa lista em que: o primeiro elemento será o comando, e os restantes elementos serão os argumentos
		if the_list:				##se a lista não for vazia, i.e. se contem algum comando processa-a
									##nesta versão apenas são utilizados os comandos G0 e G1, e respectivos argumentos.
			if (the_list[0]=="G0") or (the_list[0]=="G1"):
	##			print ">>G0... "			  ##por exemplo: G0 F3600 X71.524 Y78.072 Z0.2
												##aqui, o primeiro caracter (arg[0]) é F/X/Y/Z... de acordo com o nome do parâmetro; os caracteres seguintes (arg[1:]) contêm o valor respectivo do parâmetro (de acordo com a convenção do gcode).
				try:
					for arg in the_list:
						if arg[0]=="F":			 ##F por convenção em gcode é "feed rate", então vamos definir a variável feed_rate com o valor do argumento respectivo;
							feed_rate=float(arg[1:])
						if arg[0]=="X":			 ##aqui, se leu X como o 1º caracter, obtem o valor de X nos caracteres seguintes;
							x_point=float(arg[1:])
						if arg[0]=="Y":			 ##para Y;
							y_point=float(arg[1:])
						if arg[0]=="Z":			 ##para Z.
							z_point=float(arg[1:])
						if (the_list[0]=="G1"):
							if arg[0]=="E":
								e_length=float(arg[1:])	

				except:
					line_number_filegcode=index+1
					number_of_warnings+=1
					print('WARNING: unexpected command on the input file at line #'+ str(line_number_filegcode) +':\n\t'+str(cur_l))
					if in_force:
						print('>>> will try to continue...')
						if 'feed_rate' in vars():
							pass
						else:
							print('could not continue: no feedrate given.')
							exit()
						index+=1
						if index<len(lines):
							cur_l=lines[index]
						else:
							cur_l='eof.'
						continue
					else:
						print('program ended.')
						exit()
										
					
				delta_x=x_point-x_point_prev	 ##calcula o valor de delta_x, delta_y, e delta_z percorridos com esta instrução
				delta_y=y_point-y_point_prev
				delta_z=z_point-z_point_prev
				
				distance=sqrt(delta_x**2+delta_y**2+delta_z**2)	 ##calcula a distância percorrida com esta instrução
				time_mins+=distance/feed_rate					   ##nesta fase, antes de calcular o extra_time(), assume-se um sistema ideal: em que a velocidade seja igual à feed_rate (como se a velocidade mudasse instantaneamente para o valor desejado, o que não ocorre na prática; na prática, a velociade muda de acordo com a aceleração dos motores...)
				
				
				x_point_prev=x_point			 ##guarda os valores X, Y, e Z 
				y_point_prev=y_point
				z_point_prev=z_point

				list_G0sG1s.append((x_point, y_point, z_point, feed_rate, e_length, distance))
				index_G0G1+=1

			else:
				##comando descartado:
##			  print cur_l
				pass
			
		index+=1
		if index<len(lines):
			cur_l=lines[index]
		else:
			cur_l='eof.'

	f.close()
	return list_G0sG1s




def print_actions(list_G0sG1s, block_buffer):
	i=0
	for i in range(len(block_buffer)):
		if verbose:
			print('\n\nGCODE commands:\n'+str(list_G0sG1s[i][0:-1]))
			print(block_buffer[i])
##	  ##input()	 ## --pause.
		i+=1




def check_instructions(element):
	global t_total, t_1st, t_2nd, t_3rd, t_e0
	
	i=0
	verbose_checkinstructions=0

	if verbose:
		print("\n\n\n\n##############################\n############################## begin check_instructions()...");

	v_i = element.entry_speed			   ## obtem-se a velocidads inicial (velocidade de entrada), e a velocidade final (velocidade de saída), para o bloco actual
##		v_f = block_buffer[i+1].entry_speed   ## v_f (linha para a versão anterior com checks de consistência)
	

	if verbose:
		print(">>>>>>> "+str(element.millimeters))

	
	delta_mm_1st = element.accelerate_until_mm									  ## obtem-se a distância de aceleração
	delta_mm_3rd = element.delta_mm - element.decelerate_after_mm				   ## obtem-se a distância de desaceleração
	delta_mm_2nd = element.delta_mm - delta_mm_3rd - delta_mm_1st				   ## obtem-se a distância de plateau

	if delta_mm_1st>0:
		if verbose or verbose_checkinstructions:
			print("tem ACELERAÇÃO... durante:\n\t\t"+str(delta_mm_1st)+"mm")
	if delta_mm_2nd>0:
		if verbose or verbose_checkinstructions:
			print("tem PLATEAU... durante:\n\t\t"+str(delta_mm_2nd)+"mm")


	if delta_mm_3rd>0:
		if verbose or verbose_checkinstructions:
			print("tem DESACELERAÇÃO... durante:\n\t\t"+str(delta_mm_3rd)+"mm")

	if verbose or verbose_checkinstructions:
		print("element.delta_mm: "+str(element.delta_mm))
		print("deslocação: "+str(delta_mm_1st+delta_mm_2nd+delta_mm_3rd)+"mm")
	
	if element.delta_mm:
		delta_mm_1st *= element.millimeters/element.delta_mm
		delta_mm_2nd *= element.millimeters/element.delta_mm
		delta_mm_3rd *= element.millimeters/element.delta_mm

	if element.e_only==True:
##		  v_e0 = (mean([element.entry_speed, block_buffer[i+1].entry_speed])*0.70+element.nominal_speed*0.30)
							## (*) 1ª hipótese:
							##	  cálculo da média aritmética entre as velocidades de entrada e de saída, e média aritmética ponderada com factores de 100.0% e 0.0% para o valor anterior da média das velocidades e o valor da velocidade feedrate;
		v_e0 = (mean([element.entry_speed])*0.70+element.nominal_speed*0.30)		## (*) 2ª hipótese:
																					##	  usando apenas as propriedades do bloco actual.
		t_current_e0 = element.millimeters/(v_e0/60.0)
		
		for i in range(3):			  ## aqui quer-se que seja compatível com a função plot_graphs() que faz o plot de 6 em 6pontos.
			speed_t.append(v_e0)
			acceleration_t.append(0.0)
			t.append(t_total)
		for i in range(3):
			speed_t.append(v_e0)
			acceleration_t.append(0.0)
			t.append(t_total+t_current_e0)
	
		t_e0 += t_current_e0
		t_total += t_current_e0

		return (speed_t, acceleration_t, t)
						## salta para a iteração seguinte, porque o tempo neste caso apenas depende do eixo E0 (prosseguindo daria NaNs, porque há variáveis c/ valor 0.)

	
	'''cur_direction = v_f-v_i
	if cur_direction>=0:
		signal=1
	else:
		signal=-1		## /?\
	if verbose:
		print("SIGNAL: "+str(signal))

		print("VAR...: ")
		print(v_i)'''
	
	if delta_mm_1st>0:		  ## se tem aceleração:
		delta_t_1st = ((-v_i/60.0 + sqrt((v_i/60.0)**2-4.0*0.5*ACCELERATION_const*(-delta_mm_1st)))/(ACCELERATION_const))	   ## obtem-se o delta_t de acordo com a fórmula resolvente, t=(-b+/-sqrt(b^2-4.0*a*c))/(2.0*a) aplicada à eq. para o movimento uniformemente variado: x=x0+vx0*t+0.5*a_cons*t^2
		v_a = (v_i+ACCELERATION_const*60.0*delta_t_1st)																		 ## obtem-se a velocidade no 1º ponto intermédio do trpezoide
		if verbose or verbose_checkinstructions:
			print("VARs...: ")
			print("\tv: "+str(v_a))
			print("\tdelta_t: "+str(delta_t_1st))
	else:
		delta_t_1st=0.0
		v_a=v_i
	speed_t.append(v_i)		 ## para fazer os gráficos em função de t:
								## armazenam-se a velocidade, a aceleração e o tempo - por cada segmento do trapezoide há 2 pontos
	acceleration_t.append(ACCELERATION_const)
	t.append(t_total)
	speed_t.append(v_a)
	acceleration_t.append(ACCELERATION_const)
	t.append(t_total+delta_t_1st)

	
	if delta_mm_2nd>0:		  ## se tem plateau:
		if v_a!=0.0:
			delta_t_2nd = delta_mm_2nd/(v_a/60.0)	   ## calcula-se o tempo que demora no plateau
		else:
			delta_t_2nd = 0
		if verbose or verbose_checkinstructions:
			print("VARs...: ")
			print("\tv: "+str(v_a))
			print("\tdelta_t: "+str(delta_t_2nd))
	else:
		delta_t_2nd = 0
	speed_t.append(v_a)		 ## para fazer os gráficos em função de t
								## armazenam-se a velocidade, a aceleração e o tempo - por cada segmento do trapezoide há 2 pontos
	acceleration_t.append(0.0)
	t.append(t_total+delta_t_1st)
	speed_t.append(v_a)
	acceleration_t.append(0.0)
	t.append(t_total+delta_t_1st+delta_t_2nd)

	
	if delta_mm_3rd>0:		  ## se tem desaceleração:
		try:
			delta_t_3rd = ((-v_a/60.0 + sqrt((v_a/60.0)**2-4.0*0.5*(-ACCELERATION_const)*(-delta_mm_3rd)))/(-ACCELERATION_const))	   ## obtem-se o delta_t de acordo com a fórmula resolvente, t=(-b+/-sqrt(b^2-4.0*a*c))/(2.0*a) aplicada à eq. para o movimento uniformemente variado: x=x0+vx0*t+0.5*a_cons*t^2
		except:
			##print("WARNING: math domain error!")	  ## this exception occurs here when the argument of sqrt() is approx. 0, but due to numerical errors it is a very very small negative float instead of 0.
			delta_t_3rd = 0
		v_b = (v_a-ACCELERATION_const*60.0*delta_t_3rd)
		if verbose or verbose_checkinstructions:
			print("VARs...: ")
			print("\tv: "+str(v_b))
			print("\tdelta_t: "+str(delta_t_3rd))
	else:
		delta_t_3rd = 0
		v_b=v_a
	speed_t.append(v_a)		 ## para fazer os gráficos em função de t
								## armazenam-se a velocidade, a aceleração e o tempo - por cada segmento do trapezoide há 2 pontos
	acceleration_t.append(-ACCELERATION_const)
	t.append(t_total+delta_t_1st+delta_t_2nd)
	speed_t.append(v_b)
	acceleration_t.append(-ACCELERATION_const)
	t.append(t_total+delta_t_1st+delta_t_2nd+delta_t_3rd)
	
		
	v_f_bufferdata = v_b		## esta é a velocidade calculada com base nas propriedades definidas no buffer...
	
	'''block = element
	delta_t = delta_t_1st+delta_t_2nd+delta_t_3rd
	if delta_t!=0:
		if verbose:
			print("(delta_x, delta_y, delta_z) [mm]: ("+str(block.delta_mm_x)+", "+str(block.delta_mm_y)+", "+str(block.delta_mm_z)+")")

		try:
			v_x = sqrt(v_f**2-sum([block.delta_mm_y**2+block.delta_mm_z**2])/(60.0*delta_t**2))	 ## estas eqs. deduzem-se de: |v|=sqrt{vx^2+vy^2+vz^2}
			v_y = sqrt(v_f**2-sum([block.delta_mm_x**2+block.delta_mm_z**2])/(60.0*delta_t**2))
			v_z = sqrt(v_f**2-sum([block.delta_mm_x**2+block.delta_mm_y**2])/(60.0*delta_t**2))
		except:
			v_x = 0	 ##tmp. /!\
			v_y = 0
			v_z = 0
		if verbose:
			print("v_x: "+str(v_x))
			print("v_y: "+str(v_y))
			print("v_z: "+str(v_z))
		v=sqrt(v_x**2+v_y**2+v_z**2)
		if verbose:
			print("v: "+str(v))
		v_f_proj = max([v_x, v_y, v_z])
	else:
		v_f_proj = 0
'''		
	
	if verbose or verbose_checkinstructions:
		print("############# v_f: "+str(v_f))
		print("############# v_f_cálculo_adicional: "+str(v_f_bufferdata))
		##print("############# max{v_f_proj}: "+str(v_f_proj)+"\n")
	
	'''
	if (v_f!=0.0) and (v_f_proj!=0.0):
		f=v/v_f_proj
	else:
		f=1.0
'''
	t_segment = (delta_t_1st+delta_t_2nd+delta_t_3rd)
	t_1st += delta_t_1st
	t_2nd += delta_t_2nd
	t_3rd += delta_t_3rd
	
	##if element.nominal_speed:
	##	d = element.millimeters
	##	t_tmp = d/(element.nominal_speed/60.0)
	##else:
	##	t_tmp = 0
	t_total += t_segment
	if verbose or verbose_checkinstructions:
		##print(">>>>>>> "+str(d))
		
		print("iteração i: "+str(i))
		print("time (s): "+str(t_segment)+"\n\n")
		input()			 ##-->pause

	i+=1
	
	return (speed_t, acceleration_t, t)


		
		
def plot_graphs(speed_t, acceleration_t, t):
	n=len(t)
	f = pylab.plt.figure()
	for i in range(0, len(t), 6):   ##são 6 pontos porque: há 3 segmentos (aceleração, plateau, e desaceleração), e cada segmento tem dois pontos (início e fim).
		pylab.plot(t[i:i+6], speed_t[i:i+6], "*-")
		f.show()
		input_str=input("PAUSED: press <enter> to continue... (or \"x\"+<enter> to skip this fig.) ")		 ##-->pause to observe plots...
		if input_str.lower()=="x":
			break
		
	f = pylab.plt.figure()
	for i in range(0, len(t), 6):
		pylab.plot(t[i:i+6], acceleration_t[i:i+6], "*-")
		f.show()
		input_str=input("PAUSED: press <enter> to continue... (or \"x\"+<enter> to skip this fig.) ")		 ##-->pause to observe plots...
		if input_str.lower()=="x":
			break
	
	
		
		
def print_time(t_total):
	time_mins = t_total/60.0
	hours=floor(time_mins/60)				   ##converter o tempo de minutos p/ "hours:mins, seconds".
	mins=floor(time_mins%60)
	seconds = (time_mins-floor(time_mins))*60

	print("estimated time:\n\t"+str(int(hours))+"h:"+str(int(mins))+"m, %.3fs\n" %seconds)




if __name__ == "__main__":
	main_beeestimator()
	if number_of_warnings==0:
		print('program ended successfully.')
	else:
		print('program ended with '+str(number_of_warnings)+' warning(s).')
