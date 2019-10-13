# profile-gitsync

Profile the 'git sync' operation in Plastic SCM.

# Usage

- Install Plastic SCM + local server
- Ensure you have access to Unreal Engine in GitHub
- Create a `results` directory
- Run `clone_and_profile.bat <github username> <github password>`, let it run for as long as you have patience
- Run `analyze_log.bat` to get results
- Inspect `results\*.csv` files to see the profiling results
