#!/bin/bash
# Check if both pipelines have completed and provide summary

FLOYDADA_LOG="/private/tmp/claude-501/-Users-corey-ck-projects-kcci-maintenance/tasks/b1f3a50.output"
WINK_LOG="/private/tmp/claude-501/-Users-corey-ck-projects-kcci-maintenance/tasks/bbf6ec0.output"

echo "=========================================================================="
echo "Pipeline Completion Check"
echo "=========================================================================="
echo

# Check Floydada
FLOYDADA_DONE=0
if grep -q "✅ Pipeline complete" "$FLOYDADA_LOG" 2>/dev/null; then
    FLOYDADA_DONE=1
    echo "✅ Floydada Pipeline: COMPLETE"

    # Extract key metrics
    echo "   Metrics:"
    grep "Total tickets:" "$FLOYDADA_LOG" | tail -1
    grep "Geocoded:" "$FLOYDADA_LOG" | tail -1
    grep "Success rate:" "$FLOYDADA_LOG" | tail -1

    echo "   Outputs:"
    grep "Results saved to:" "$FLOYDADA_LOG" | tail -1
    grep "Maintenance estimate saved to:" "$FLOYDADA_LOG" | tail -1
elif grep -q "❌" "$FLOYDADA_LOG" 2>/dev/null; then
    echo "❌ Floydada Pipeline: ERROR"
    echo "   Last 10 lines:"
    tail -10 "$FLOYDADA_LOG" | sed 's/^/     /'
else
    echo "⏳ Floydada Pipeline: STILL RUNNING"
    tail -3 "$FLOYDADA_LOG" | sed 's/^/   /'
fi

echo

# Check Wink
WINK_DONE=0
if grep -q "✅ Pipeline complete" "$WINK_LOG" 2>/dev/null; then
    WINK_DONE=1
    echo "✅ Wink Pipeline: COMPLETE"

    # Extract key metrics
    echo "   Metrics:"
    grep "Total tickets:" "$WINK_LOG" | tail -1
    grep "Geocoded:" "$WINK_LOG" | tail -1
    grep "Success rate:" "$WINK_LOG" | tail -1

    echo "   Outputs:"
    grep "Results saved to:" "$WINK_LOG" | tail -1
    grep "Maintenance estimate saved to:" "$WINK_LOG" | tail -1
elif grep -q "❌" "$WINK_LOG" 2>/dev/null; then
    echo "❌ Wink Pipeline: ERROR"
    echo "   Last 10 lines:"
    tail -10 "$WINK_LOG" | sed 's/^/     /'
else
    echo "⏳ Wink Pipeline: STILL RUNNING"
    tail -3 "$WINK_LOG" | sed 's/^/   /'
fi

echo
echo "=========================================================================="

# Summary
if [ $FLOYDADA_DONE -eq 1 ] && [ $WINK_DONE -eq 1 ]; then
    echo "🎉 BOTH PIPELINES COMPLETE!"
    echo
    echo "Generated Files:"
    echo "----------------"
    echo
    echo "Floydada:"
    ls -lh projects/floydada/outputs/*.csv projects/floydada/outputs/*.xlsx 2>/dev/null | tail -2 | awk '{print "  ", $9, "("$5")"}'
    echo
    echo "Wink:"
    ls -lh projects/wink/outputs/*.csv projects/wink/outputs/*.xlsx 2>/dev/null | tail -2 | awk '{print "  ", $9, "("$5")"}'
    echo
    echo "=========================================================================="
    echo "Next Steps:"
    echo "1. Review PIPELINE_RUN_SUMMARY.md for details"
    echo "2. Open maintenance estimates to verify formulas"
    echo "3. Check geocoding success rates"
    echo "=========================================================================="
elif [ $FLOYDADA_DONE -eq 1 ] || [ $WINK_DONE -eq 1 ]; then
    echo "⏳ One pipeline complete, one still running..."
    echo
    echo "Estimated remaining time: 5-15 minutes"
else
    echo "⏳ Both pipelines still running..."
    echo
    echo "Check again in a few minutes with: ./check_completion.sh"
fi

echo
