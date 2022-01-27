import math
import unittest
import sys
import os
import time

import numpy as np

print('Python %s on %s' % (sys.version, sys.platform))
from pathlib import Path

sys.path.append(Path(os.path.abspath(__file__)).parents[2].__str__())

from utils.Simulate_swarm_population import simulate_swarm_with_restart_population
from utils import Individual


class TestSim(unittest.TestCase):
    def test_sim(self, controller_type="Rand", headless=False):
        genotype = Individual.thymio_genotype("NN", 9, 2)
        # genotype = Individual.thymio_genotype("4dir", 7, 2)
        # genotype = Individual.thymio_genotype(controller_type, 7, 2)
        #x_best_data = np.load("./results/NN_reservoir_min3_10x50/0/x_best.npy")[-1]
        x_best_data = np.array([-1.04915947, 5.59031084, -7.49548435, -0.2405773, 1.55864411 , 1.7725805,
        -1.1781353,  1.92587801,  4.80432718 , 2.47523886 , 6.10147554  ,6.59721802,
        -0.15279066, -3.54256163 ,-0.1205002,  -2.19433711 ,-2.98661291, -2.12080928])
        # x_best_data = np.random.uniform(-5, 5, 100)
        genotype['controller']["encoding"] = x_best_data
        genotype['controller']["params"]['torch'] = False
        individual = Individual.Individual(genotype, 0)
        individual.controller.load_geno("/home/lj/EC_swarm/results")
        individual.geno2pheno(x_best_data)
        tic = time.perf_counter()
        try:
            t_avg = 0
            for _ in range(10):
                fitness = simulate_swarm_with_restart_population(600, [individual], False, [1, 1, 1, 1, 1])
                toc = time.perf_counter()
                t_avg += (toc - tic) / 10
                tic = toc
        except:
            raise Exception("Could not calculate fitness")
        print(f"Average Simulate_Swarm running time: {t_avg:0.4f} seconds")
        self.assertEqual(fitness > 0, True)


if __name__ == '__main__':
    print("STARTING")
    unittest.main()
    print("FINISHED")
