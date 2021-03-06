# -*- coding: utf-8 -*-
"""
Created on Sun Apr 24 10:44:11 2016

@author: evan87
"""

import pandas as pd
import pandas.io.data as web
import datetime
import time
import os
import json
from pandas import read_hdf

# after the calculation of the techical indication are stable, we should store them in the database as well
# so we don't need to do the calculation later on

class lm_stock:
    
    '''A customer of ABC Bank with a checking account. Customers have the
       following properties:

    Attributes:
        name: A string representing the customer's name.
        balance: A float tracking the current balance of the customer's account.
    '''
    
    def __init__(self):
        
        self.symbol = '^IXIC'
        
        self.start  = '1/1/1900'
        
        self.end    = '4/22/2015'
        
        self.dataFile = 'stock_data.h5s'
        
        self.dataPath = os.getcwd() + '/'
        
        
    def is_in_hdf5store(self):
        
        meta_data = self.__getMetaData__()
        
        if self.symbol in meta_data:            
            return True            
        else :
            return False 
                    
    def print_stock_statistics(self):
        
        if self.is_in_hdf5store() == False :
            print "No record of stock %s found in database" %(self.symbol)
            exit(0)
        
        data =read_hdf(self.dataFile, self.symbol)
        
        print data.info()
            
    def get_stock_indicator(self,start,end):
        
        data =read_hdf(self.dataFile, self.symbol,where='index>=start & index <= end')
        
        data['ma5']  = pd.rolling_mean(data['Adj Close'], window=5).bfill()
        data['ma20'] = pd.rolling_mean(data['Adj Close'], window=20).bfill()
        data['ma50'] = pd.rolling_mean(data['Adj Close'], window=50).bfill()

        data['bol_upper'] = pd.rolling_mean(data['Adj Close'], window=20).bfill() + 2* pd.rolling_std(data['Adj Close'], 20, min_periods=20).bfill()
        data['bol_lower'] = pd.rolling_mean(data['Adj Close'], window=20).bfill() - 2* pd.rolling_std(data['Adj Close'], 20, min_periods=20).bfill()      
        data['bol_bw'] = ((data['bol_upper'] - data['bol_lower'])/data['ma20'])*100
        
                
        data['exma12'] = pd.ewma(data['Adj Close'], span=12).bfill()
        
        data['exma26'] = pd.ewma(data['Adj Close'], span=26).bfill()
        
        data['dif'] = data['exma12'] - data['exma26']
        
        data['dea'] = pd.ewma(data['dif'],span=9).bfill()
        
        data['macd'] = (data['dif'] - data['dea']) * 2
        
        #seems 百度百科对KDJ的算法介绍是错误的
        data['k'] = ((data['Adj Close'] - pd.rolling_min(data['Adj Close'],window=9).bfill())/
                     (pd.rolling_max(data['Adj Close'],window=9).bfill()-pd.rolling_min(data['Adj Close'],window=9).bfill()))*100
        
        data['d'] = pd.ewma(data['k'],span=3).bfill()
        
        data['j'] = 3 * data['d'] - 2 * data['k']
        

        return data        
        
        
    def get_stock_return(self,start,end):
        
        #maybe we can get the log daily return (any return betwen the days will just be a minus operation after)
        if self.is_in_hdf5store() == False :
            print "No record of stock %s found in database" %(self.symbol)
            exit(0)
            
        data =read_hdf(self.dataFile, self.symbol,where='index>=start & index <= end',columns=['Adj Close',])
        
        if data is None:
            print "No record of stock %s found in database from %s to %s, please update the database" %(self.symbol,start,end)
            exit(0)
        
        return (data['Adj Close'][-1]/data['Adj Close'][0] - 1, data['Adj Close'][0],data['Adj Close'][-1] )

    def get_stock_data (self):

        try:            
            data = web.DataReader(self.symbol, data_source = 'yahoo', start=self.start,end=self.end)        
        except:    
            err_file = open('err.log','a')
            err_file.write("lm_stock::get_stock_data: Getting an error during web data fetch for stock %s\n" %self.symbol)
            err_file.close()
                         
            return None
            
        return data
        
    def get_local_stock_data (self):

        try:            
            meta_data = self.__getMetaData__()            
            if self.symbol in meta_data :                
                end_date = meta_data[self.symbol]                
            else :
                err_file = open('err.log','a')
                err_file.write("lm_stock::get_local_stock_data: stock is not present in local database!\n") 
                err_file.close()
                exit(0)
                
            saved_end_date = time.strptime(end_date, "%d/%m/%Y")
        
            new_end_date   = time.strptime(self.end, "%d/%m/%Y")
            
            if new_end_date > saved_end_date : 
                err_file = open('err.log','a')
                err_file.write("lm_stock::get_local_stock_data: stock info is not up2date in local database!\n")
                err_file.close()
            else :
                #read from hdf5           
                data =read_hdf(self.dataFile, self.symbol)
                        
        except:
            err_file = open('err.log','a')
            err_file.write("lm_stock::get_stock_data: Getting an error during local data fetch for stock %s\n" %self.symbol)   
            err_file.close()
            return None
            
        return data
    
    def create_hdf5store (self,data):
    
        #TODO if the store already exists, don't flush it
        #and print out a warning
        
        print "Creating %s @ %s for stock %s" %(self.dataFile ,self.dataPath,self.symbol) 
        
        h5s = pd.HDFStore(self.dataFile)
        
        #h5s.put(self.symbol,data)
        #h5s[self.symbol] = data
        
        h5s.append(self.symbol,data)
        
        #let's put the meta data inside json file

        #print h5s
        
        file_name = self.dataFile.split('.')[0] + '.json'

        print "JSON file name is ", file_name
        
        #meta data records the last date when stock in hdf5store gets updated
        
        meta_data = self.__getMetaData__()
                        
        meta_file = open(self.dataPath+file_name, 'w')
            
        meta_data[self.symbol] = self.end
        
        json.dump(meta_data,meta_file)
        
        meta_file.close()
        
        h5s.close()
        
        
    def update_hdf5store(self):
        
        #TODO what if error happends, just log it and continue...    
        meta_data = self.__getMetaData__()
        
        last_end_date = meta_data[self.symbol]
        
        today = self.__getTodayDate__()
        
        saved_date = time.strptime(last_end_date, "%m/%d/%Y")
        
        new_date   = time.strptime(today, "%m/%d/%Y")
        
        if new_date > saved_date:
            
            print "Updating %s @ %s for stock %s" %(self.dataFile ,self.dataPath,self.symbol)
            
            data = web.DataReader(self.symbol, data_source = 'yahoo', start=last_end_date,end=today)
            #first row is a duplicate
            h5s = pd.HDFStore(self.dataFile)
            
            h5s.append(self.symbol,data[1:])
            
            file_name = self.dataFile.split('.')[0] + '.json'
            
            meta_file = open(self.dataPath+file_name, 'w')
            
            meta_data[self.symbol] = today
            
            json.dump(meta_data,meta_file)
            
            meta_file.close()
            
            h5s.close()
                        
#private methods
            
    def __getTodayDate__(self):
        
        date=str(datetime.date.today())
        
        date = date.split('-')
        
        date = date[1] + '/'+date[2] + '/'+date[0]
        
        return date
        
        
    def __getMetaData__(self):
        
        meta_data = dict()
        
        file_name = self.dataFile.split('.')[0] + '.json'
        
        if os.path.exists(self.dataPath+file_name):
            
            meta_file = open(self.dataPath+file_name, 'r')
                        
            meta_data = json.loads(meta_file.read())
            
            meta_file.close()
        
        return meta_data
        
        
        
        
    
    
    

