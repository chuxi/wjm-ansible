#!/bin/bash

if [[ $# < 2 ]]; then
  echo "usage: benchmark.sh [mode:none|rocksdb] [dataset:huge|gigantic|bigdata] [filter level:0.8]"
  exit 1
fi

mode=$1
dataset=$2

if [ $# == 3 ]; then
  filter="where adRevenue >= $3"
else
  filter=""
fi

SPARK_HOME=~/svr/spark

table="uservisits_$dataset"

filename="benchmark-$mode-$dataset.txt"

cat > $filename << EOF
import org.apache.spark.sql.SparkSession

def fullScan(spark: SparkSession, counter: Int): Unit = {
  spark.sql(s"cache table $table")
  // make cache work
  spark.table("$table").count()

  val sql = s"select * from $table $filter"

  var total: Long = 0
  for (i <- 0 until counter) {
    val start = System.nanoTime()
    spark.sql(sql)
      .queryExecution.toRdd
      .foreach(_ => Unit)
    val end = System.nanoTime()
    val milliseconds = (end - start) / 1000 / 1000
    println(s"\$i running time: \$milliseconds ms")
    total = total + milliseconds
  }
  println(s"avg running time: \${total / counter} ms")
}

val counter = 5

fullScan(spark, counter)
spark.sharedState.cacheManager.clearCache()

sys.exit(0)

EOF


$SPARK_HOME/bin/spark-shell -i $filename \
  --files $SPARK_HOME/conf/zs.prop \
  --conf spark.windjammer.tableCache.kvstore=$mode \
  --conf spark.metrics.namespace=$mode
