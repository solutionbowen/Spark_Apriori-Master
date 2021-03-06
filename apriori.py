# -*- coding: UTF-8 -*-
from pyspark import SparkContext
from pyspark import SparkConf

def SetLogger( sc ):
    logger = sc._jvm.org.apache.log4j
    logger.LogManager.getLogger("org"). setLevel( logger.Level.ERROR )
    logger.LogManager.getLogger("akka").setLevel( logger.Level.ERROR )
    logger.LogManager.getRootLogger().setLevel(logger.Level.ERROR)   

def SetPath(sc):
    global Path
    if sc.master[0:5]=="local" :
        Path="file:/home/paul/pythonwork/PythonProject/"
    else:   
        Path="hdfs://140.120.32.236:9000/user/paul/"
        
def CreateSparkContext():
    sparkConf = SparkConf()                                                       \
                         .setAppName("Spark Apriori")                         \
                         .set("spark.testing.memory", "2147480000")\
                         .set("spark.ui.showConsoleProgress", "false") \
    
    sc = SparkContext(conf = sparkConf)
    print("master="+sc.master)
    SetLogger(sc)
    SetPath(sc)
    return (sc)
    
def findFrequentItemsets(input, output, numPartitions, s, sc):
    #讀取HDFS資料
    data = sc.textFile(input, numPartitions)
    #原始資料筆數(行數)
    count = data.count()
    #RDD分區數
    numPartitions = data.getNumPartitions()
    #支持個數 = 支持度(%)*原始資料筆數
    threshold = 0.4*count
    #將原始資料一行一行讀進來，每一行對空格切割，切割完後轉換成整數由小到大排列
    myDat = data.map(lambda line: sorted([int(y) for y in line.strip().split(' ')]))
    #將myDat每行資料的單一項目集全部集中，然後去除掉重複部分，形成1_候選項目集
    C1=myDat.flatMap(lambda x: set(x)).distinct().collect()
    #將C1裡面的元素轉換成frozenset形式
    #需要這樣做，因為python的代碼裡需要處理集合操作 
    C1=[frozenset([var]) for var in C1]
    #將myDat每一行的原始資料分別轉換成set()形式，之後要反覆搜尋原始資料判斷是否為高頻用
    D=myDat.map(lambda x: set(x)).collect()
    #將D轉換成廣播變數
    D_bc=sc.broadcast(D)
    #獲取原始資料行數(轉換成float形式))
    length=len(myDat.collect())*1.0
    #將C1轉換成SparkContext形式(創建RDD)
    suppData1=sc.parallelize(C1)
    #將C1(1_候選項目集)中每個元素分別去跟原始資料做比較(判斷是否為子集合)，若是子集合會加到list中
    #最後得到的list長度為此(1_候選項目集)的支持個數，再除以原始資料的長度為支持度
    #以支持度來判斷，濾掉低於支持度的(1_候選項目集)，最後得到(1_高頻項目集, 支持度)
    suppData=sc.parallelize(C1).map(lambda x: (x,len([var for var in D_bc.value if x.issubset(var)])/length) if len([var for var in D_bc.value if x.issubset(var)])/length >=s else ()).filter(lambda x: x).collect()
    #宣告一個list
    L=[]
    #將suppData取出1_高頻項目集的部分放到L1中
    L1=[frozenset(var) for var in map(lambda x:x[0],suppData)]
    #把L1加到L裡
    L.append(L1)
    #將1_高頻項目集以及支持個數輸出至檔案存到HDFS中
    suppDataout1=sc.parallelize(suppData)
    finalItemSets1 = suppDataout1.map(lambda (itemset, count): ", ".join([str(x) for x in itemset])+"\t("+str(count)+")")
    finalItemSets1.saveAsTextFile("data/output/1")
    print("1_高頻項目集已存至HDFS中")
    k=2  
    #D_bc=sc.broadcast(D)  
    #while迴圈，先判斷有沒有長度為k的高頻項目集，若有則進入迴圈
    while (len(L[k-2])>0):  
        #產生長度為k+1的候選項目集
        Ck=[var1|var2 for index,var1 in enumerate(L[k-2]) for var2 in L[k-2][index+1:] if list(var1)[:k-2]==list(var2)[:k-2]]  
        #產生長度為k+1的高頻項目集
        suppData_temp=sc.parallelize(Ck).map(lambda x: (x,len([var for var in D_bc.value if x.issubset(var)])/length) if len([var for var in D_bc.value if x.issubset(var)])/length >=s else ()).filter(lambda x: x).collect()  
        #Ck中的多個子集會分佈到多個分佈的機器的任務中運行，D_bc是D的分發共用變數，在每個任務中，都可以使用D_bc來統計本任務中包含某子集的個數  
        suppData+=suppData_temp
        if len(suppData_temp) > 0:
			suppDataoutk=sc.parallelize(suppData_temp)
            finalItemSetsk = suppDataoutk.map(lambda (itemset, count): ", ".join([str(x) for x in itemset])+"\t("+str(count)+")")
            outputdir = "data/output/" + str(k)
            finalItemSetsk.saveAsTextFile(outputdir)
            print( str(k) + "_高頻項目集已存至HDFS中")
        L.append([var[0] for var in suppData_temp]) #使用这行代码，最后跳出while后再过滤一下空的项  
        k+=1  
    L=[var for var in L if var]  
    print(L)  
    print(suppData) 
    
    
    
    
    

if __name__ == "__main__":
    print("開始執行Apriori")
    sc=CreateSparkContext()
    f_input = Path + "data/retail.txt"
    f_output = Path + "data/output"
    threshold = 0.1
    numPartitions = 3
    
    findFrequentItemsets(f_input, f_output, numPartitions, threshold, sc)
    sc.stop()