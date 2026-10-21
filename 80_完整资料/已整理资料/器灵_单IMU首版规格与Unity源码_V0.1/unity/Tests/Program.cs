using System;
class Program { static int Main(){try{SpiritIMU.CoreSelfTest.Run();Console.WriteLine("PASS: SpiritIMU C# core self-tests executed.");return 0;}catch(Exception e){Console.Error.WriteLine(e);return 1;}} }
