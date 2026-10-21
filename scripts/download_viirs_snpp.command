#!/bin/zsh
task_root="${0:A:h:h}"
cd "$task_root" || exit 1
"$task_root/.venv/bin/python" -u "$task_root/scripts/download_viirs_snpp.py"
task_result=$?
echo ""
echo "Download process exited with status $task_result."
echo "Press Return to close this terminal window."
read -r task_reply
exit "$task_result"
