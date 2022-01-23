#!/usr/bin/env python3
from future.utils import iteritems

import random
import sys

from jmbase import get_log, jmprint, EXIT_ARGERROR
from jmbitcoin import amount_to_str
from jmclient import YieldGeneratorBasic, ygmain, jm_single

# This is a maker for the purposes of generating a yield from held bitcoins
# while maximising the difficulty of spying on blockchain activity.
# This is primarily attempted by randomizing all aspects of orders
# after transactions wherever possible.

# YIELD GENERATOR SETTINGS ARE NOW IN YOUR joinmarket.cfg CONFIG FILE
# (You can also use command line flags; see --help for this script).

jlog = get_log()

class YieldGeneratorPrivacyEnhanced(YieldGeneratorBasic):

    def __init__(self, wallet_service, offerconfig, cswallet_service = None, csconfig = None):
        super().__init__(wallet_service, offerconfig, cswallet_service, csconfig)
        
    def select_input_mixdepth(self, available, offer, amount):
        """Mixdepths are in cyclic order and we select the mixdepth to
        maximize the largest interval of non-available mixdepths by choosing
        the first mixdepth available after the largest such interval.
        This forces the biggest UTXOs to stay in a bulk of few mixdepths so
        that the maker can always maximize the size of his orders even when
        some coins are sent from the last to the first mixdepth"""
        # We sort the available depths for linear scaling of the interval search
        available = sorted(available.keys())
        # For an available mixdepth, the smallest interval starting from this mixdepth
        # containing all the other available mixdepths necessarily ends at the previous
        # available mixdepth in the cyclic order. The successive difference of sorted
        # depths is then the length of the largest interval ending at the same mixdepth
        # without any available mixdepths, modulo the number of mixdepths if 0 is in it
        # which is only the case for the first (in linear order) available mixdepth case
        intervals = ([self.wallet_service.mixdepth + 1 + available[0] - available[-1]] + \
                    [(available[i+1] - available[i]) for i in range(len(available)-1)])
        # We return the mixdepth value at which the largest interval without
        # available mixdepths ends. Selecting this mixdepth will send the CoinJoin
        # outputs closer to the others available mixdepths which are after in cyclical order
        return available[max(range(len(available)), key = intervals.__getitem__)]

    def create_my_orders(self):
        mix_balance = self.get_available_mixdepths()
        # We publish ONLY the maximum amount and use minsize for lower bound;
        # leave it to oid_to_order to figure out the right depth to use.
        f = '0'
        if self.ordertype in ['swreloffer', 'sw0reloffer']:
            f = self.cjfee_r
        elif self.ordertype in ['swabsoffer', 'sw0absoffer']:
            f = str(self.txfee + self.cjfee_a)
        mix_balance = dict([(m, b) for m, b in iteritems(mix_balance)
                            if b > self.minsize])
        if len(mix_balance) == 0:
            jlog.error('You do not have the minimum required amount of coins'
                       ' to be a maker: ' + str(self.minsize) + \
                       '\nTry setting txfee to zero and/or lowering the minsize.')
            return []
        max_mix = max(mix_balance, key=mix_balance.get)

        # randomizing the different values
        randomize_txfee = int(random.uniform(self.txfee * (1 - float(self.txfee_factor)),
                                             self.txfee * (1 + float(self.txfee_factor))))
        randomize_minsize = int(random.uniform(self.minsize * (1 - float(self.size_factor)),
                                               self.minsize * (1 + float(self.size_factor))))
        if randomize_minsize < jm_single().DUST_THRESHOLD:
            jlog.warn("Minsize was randomized to below dust; resetting to dust "
                      "threshold: " + amount_to_str(jm_single().DUST_THRESHOLD))
            randomize_minsize = jm_single().DUST_THRESHOLD
        possible_maxsize = mix_balance[max_mix] - max(jm_single().DUST_THRESHOLD, randomize_txfee)
        randomize_maxsize = int(random.uniform(possible_maxsize * (1 - float(self.size_factor)),
                                               possible_maxsize))

        # Minimum cj fee: 100,000 * 0.003 = 300
        # Maximum cj fee: 1,000,000 * 0.003 = 3000
        order_0 = {'oid': 0,
                 'ordertype': self.ordertype,
                 'minsize': 100000,
                 'maxsize': 999999,
                 'txfee': 0,
                 'cjfee': '0.003'}

        # Minimum cj fee: 1,000,000 * 0.001 = 1000
        # Maximum cj fee: 5,000,000 * 0.001 = 5000
        order_1 = {'oid': 1,
                 'ordertype': self.ordertype,
                 'minsize': 1000000,
                 'maxsize': 4999999,
                 'txfee': 0,
                 'cjfee': '0.001'}

        if randomize_maxsize > 50000000:
            # Minimum cj fee: 5,000,000 * 0.0002 = 1000
            # Maximum cj fee: 50,000,000 * 0.0002 = 10000
            order_2 = {'oid': 2,
                     'ordertype': self.ordertype,
                     'minsize': 5000000,
                     'maxsize': 49999999,
                     'txfee': 0,
                     'cjfee': '0.0002'}

            # Minimum cj fee: 50,000,000 * 0.00002 = 1000
            order_3 = {'oid': 3,
                     'ordertype': self.ordertype,
                     'minsize': 50000000,
                     'maxsize': randomize_maxsize,
                     'txfee': 0,
                     'cjfee': '0.00002'}
            return [order_3, order_2, order_1, order_0]
        else:
            # Minimum cj fee: 5,000,000 * 0.0002 = 1000
            order_2 = {'oid': 2,
                     'ordertype': self.ordertype,
                     'minsize': 5000000,
                     'maxsize': randomize_maxsize,
                     'txfee': 0,
                     'cjfee': '0.0002'}
            return [order_2, order_1, order_0]


if __name__ == "__main__":
    ygmain(YieldGeneratorPrivacyEnhanced, nickserv_password='')
    jmprint('done', "success")
