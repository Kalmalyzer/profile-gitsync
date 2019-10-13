echo usage: runme.bat github_username github_password
echo beware that the github username and password will be stored in the output log file

md results
python clone_and_profile.py https://github.com/EpicGames/UnrealEngine.git UE4@local %1 %2
