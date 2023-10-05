import os                                                                                                                     
def save_primes(n):                                                                                                           
    primes = []                                                                                                               
    for i in range(2, n+1):                                                                                                   
        if all(i % j != 0 for j in range(2, int(i**0.5) + 1)):                                                                
            primes.append(i)                                                                                                  
    with open("primes.txt", "w") as f:                                                                                        
        f.write("\n".join(str(p) for p in primes))