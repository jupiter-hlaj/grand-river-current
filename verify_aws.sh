#!/bin/bash
mkdir -p aws_verify
echo "Function,Status,Diff" > verification_report.csv

verify_function() {
    FUNC_NAME=$1
    LOCAL_DIR=$2
    
    echo "Checking $FUNC_NAME..."
    URL=$(aws lambda get-function --function-name $FUNC_NAME --query 'Code.Location' --output text)
    curl -s -o "aws_verify/${FUNC_NAME}.zip" "$URL"
    unzip -o -q "aws_verify/${FUNC_NAME}.zip" -d "aws_verify/${FUNC_NAME}"
    
    if [ -f "aws_verify/${FUNC_NAME}/lambda_function.py" ] && [ -f "$LOCAL_DIR/lambda_function.py" ]; then
        diff -q "aws_verify/${FUNC_NAME}/lambda_function.py" "$LOCAL_DIR/lambda_function.py" > /dev/null
        if [ $? -eq 0 ]; then
            echo "$FUNC_NAME,MATCH,-" >> verification_report.csv
        else
            echo "$FUNC_NAME,MISMATCH,Diff found" >> verification_report.csv
            echo "--- DIFF FOR $FUNC_NAME ---" >> verification_diffs.txt
            diff "aws_verify/${FUNC_NAME}/lambda_function.py" "$LOCAL_DIR/lambda_function.py" >> verification_diffs.txt
            echo "---------------------------" >> verification_diffs.txt
        fi
    else
        echo "$FUNC_NAME,ERROR,Missing file" >> verification_report.csv
    fi
}

verify_function "GRT_Update_Checker" "pkg_checker"
verify_function "GRT_Ingest" "pkg_ingest"
verify_function "GRT_Static_Ingest" "pkg_static"
verify_function "GRT_Static_Ingest_StopTimes" "pkg_stop_times_ingest"
verify_function "GRT_Static_Ingest_StopSchedule" "pkg_stop_schedule"
verify_function "GRT_Logger" "pkg_logger"
verify_function "GRT_Reader" "pkg_reader"

cat verification_report.csv
