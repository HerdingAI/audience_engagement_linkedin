#!/bin/bash

# LinkedIn Automation Setup Script
# This script helps you set up the crontab for automated LinkedIn scripts

echo "=== LinkedIn Automation Setup ==="
echo ""

# Check if the main script exists and is executable
if [ ! -f "/home/buntu/Desktop/Apps/Engagement/linkedin_automation.sh" ]; then
    echo "❌ linkedin_automation.sh not found!"
    exit 1
fi

if [ ! -x "/home/buntu/Desktop/Apps/Engagement/linkedin_automation.sh" ]; then
    echo "Making linkedin_automation.sh executable..."
    chmod +x /home/buntu/Desktop/Apps/Engagement/linkedin_automation.sh
fi

echo "✅ Main automation script is ready"
echo ""

# Show current crontab
echo "Current crontab entries:"
crontab -l 2>/dev/null | grep -v "^#" | head -10

echo ""
echo "=== Setup Options ==="
echo "1. Add automation to run 4 random days per week (recommended)"
echo "2. Add automation to run every weekday with 80% chance"
echo "3. Show manual setup instructions"
echo "4. Test run the automation script now"
echo ""

read -p "Choose an option (1-4): " choice

case $choice in
    1)
        echo "Adding crontab entries for 4 random weekdays..."
        (crontab -l 2>/dev/null; echo "# LinkedIn Automation - 4 random weekdays") | crontab -
        (crontab -l; echo "0 7 * * 1 /bin/bash -c 'sleep \$((RANDOM % 9900)); /home/buntu/Desktop/Apps/Engagement/linkedin_automation.sh'") | crontab -
        (crontab -l; echo "0 7 * * 2 /bin/bash -c 'sleep \$((RANDOM % 9900)); /home/buntu/Desktop/Apps/Engagement/linkedin_automation.sh'") | crontab -
        (crontab -l; echo "0 7 * * 3 /bin/bash -c 'sleep \$((RANDOM % 9900)); /home/buntu/Desktop/Apps/Engagement/linkedin_automation.sh'") | crontab -
        (crontab -l; echo "0 7 * * 4 /bin/bash -c 'sleep \$((RANDOM % 9900)); /home/buntu/Desktop/Apps/Engagement/linkedin_automation.sh'") | crontab -
        echo "✅ Crontab entries added successfully!"
        ;;
    2)
        echo "Adding crontab entry for every weekday with built-in randomization..."
        (crontab -l 2>/dev/null; echo "# LinkedIn Automation - Every weekday with 80% chance") | crontab -
        (crontab -l; echo "0 7 * * 1-5 /home/buntu/Desktop/Apps/Engagement/linkedin_automation.sh") | crontab -
        echo "✅ Crontab entry added successfully!"
        ;;
    3)
        echo ""
        echo "=== Manual Setup Instructions ==="
        echo "1. Run: crontab -e"
        echo "2. Add one of these lines:"
        echo ""
        echo "For 4 random weekdays:"
        echo "0 7 * * 1 /bin/bash -c 'sleep \$((RANDOM % 9900)); /home/buntu/Desktop/Apps/Engagement/linkedin_automation.sh'"
        echo "0 7 * * 2 /bin/bash -c 'sleep \$((RANDOM % 9900)); /home/buntu/Desktop/Apps/Engagement/linkedin_automation.sh'"
        echo "0 7 * * 3 /bin/bash -c 'sleep \$((RANDOM % 9900)); /home/buntu/Desktop/Apps/Engagement/linkedin_automation.sh'"
        echo "0 7 * * 4 /bin/bash -c 'sleep \$((RANDOM % 9900)); /home/buntu/Desktop/Apps/Engagement/linkedin_automation.sh'"
        echo ""
        echo "OR for every weekday with built-in 80% chance:"
        echo "0 7 * * 1-5 /home/buntu/Desktop/Apps/Engagement/linkedin_automation.sh"
        echo ""
        ;;
    4)
        echo "Running test automation..."
        /home/buntu/Desktop/Apps/Engagement/linkedin_automation.sh
        echo ""
        echo "Check linkedin_automation.log for results"
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""
echo "=== Current Crontab ==="
crontab -l 2>/dev/null

echo ""
echo "=== Setup Complete ==="
echo "Your LinkedIn automation is now configured!"
echo "Logs will be stored in: /home/buntu/Desktop/Apps/Engagement/linkedin_automation.log"
echo ""
echo "To view logs: tail -f /home/buntu/Desktop/Apps/Engagement/linkedin_automation.log"
echo "To remove automation: crontab -e (and delete the LinkedIn lines)"
