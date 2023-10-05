import platform                                                                                                                                              
def get_kernel_version():                                                                                                                                    
    return platform.release()                                                                                                                                
def get_system_details():                                                                                                                                    
    return platform.uname()                                                                                                                                  
if __name__ == "__main__":                                                                                                                                   
    print(get_kernel_version())                                                                                                                              
    print(get_system_details())