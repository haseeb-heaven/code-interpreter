import platform                                                                                                                              
                                                                                                                                             
def get_system_details():                                                                                                                    
    kernel_version = platform.release()                                                                                                      
    system = platform.system()                                                                                                               
    machine = platform.machine()                                                                                                             
    processor = platform.processor()                                                                                                         
    return kernel_version, system, machine, processor                                                                                        
                                                                                                                                             
if __name__ == "__main__":                                                                                                                   
    kernel_version, system, machine, processor = get_system_details()                                                                        
    print(f"Kernel Version: {kernel_version}")                                                                                               
    print(f"System: {system}")                                                                                                               
    print(f"Machine: {machine}")                                                                                                             
    print(f"Processor: {processor}")                                                                                                         
