class RING_BUFFER():
    def __init__(self, MAX_SIZE_BUFFER):        ##cria um buffer novo vazio; e guarda o tamanho máximo do buffer (se MAX_SIZE_BUFFER for igual a "+inf", assume-se um tamanho dinâmico ~"infinito")
        self.buffer_list = []
        self.max_size = MAX_SIZE_BUFFER


    def __str__(self):                          ##prepara a impressão dos dados do buffer
        str_buffer = "BUFFER has the current size of: "+str(self.size())+"\n"
        str_buffer += "is it empty?"
        if self.is_empty():
            str_buffer += " yes.\n"
        else:
            str_buffer += " no.\n"
        str_buffer += "is it full?"
        if self.is_full():
            str_buffer += " yes.\n"
        else:
            str_buffer += " no.\n\n\n"
        str_buffer += "blocks:\n"
        for i in range(self.size()):
            str_buffer += "\t"+str(self.buffer_list[i])+"\n"
        return str_buffer
    

    def __len__(self):
        return self.size()
    
    
    def __getitem__(self, i):
        return self.buffer_list[i]
        
    
    def push(self, new_block):                  ##adiciona o elemento de input ao final da lista
        self.buffer_list.append(new_block)
    
    
    def pop(self):                              ##remove e devolve o 1º elemento da lista
        element = self.buffer_list.pop(0)
        return element
       
       
    def receive_move(self, new_block):
        if self.is_full():
            self.pop()
        self.push(new_block)
      
      
    def size(self):
        return len(self.buffer_list)


    def is_empty(self):
        return self.size()==0
    
    
    def is_full(self):
        return self.size()==self.max_size
    
