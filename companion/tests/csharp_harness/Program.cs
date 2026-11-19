// Test harness (not part of the plugin): runs the plugin's real SocketLink.cs outside VaM, so the Python tests can
// talk to it over a real loopback socket. Usage: Harness <port> <seconds>
using System;
using System.Threading;

namespace AIBody
{
    public delegate void PayloadHandler(string payload);

    public static class Log
    {
        public static void Info(string m) { Console.WriteLine("LOG " + m); }
        public static void Debug(string m) { }
        public static void Error(string m) { Console.WriteLine("LOGERR " + m); }
    }

    public static class Program
    {
        public static int Main(string[] args)
        {
            int port = int.Parse(args[0]);
            double seconds = double.Parse(args[1], System.Globalization.CultureInfo.InvariantCulture);
            SocketLink link = new SocketLink(port, (string p) => Console.WriteLine("PAYLOAD " + p));
            link.Start();
            Console.WriteLine("START blocked=" + link.Blocked + " status=" + link.Status);
            DateTime end = DateTime.UtcNow.AddSeconds(seconds);
            DateTime last = DateTime.UtcNow;
            bool wasLive = false;
            int n = 0;
            double sinceSend = 0;
            while (DateTime.UtcNow < end)
            {
                double dt = (DateTime.UtcNow - last).TotalSeconds;
                last = DateTime.UtcNow;
                link.Tick((float)dt);
                if (link.Live != wasLive)
                {
                    wasLive = link.Live;
                    Console.WriteLine("LIVE " + wasLive + " status=" + link.Status);
                }
                sinceSend += dt;
                if (link.Live && sinceSend > 0.3)
                {
                    sinceSend = 0;
                    n++;
                    link.Send("{\"type\":\"heartbeat\",\"n\":" + n + "}");
                }
                Thread.Sleep(10);
            }
            Console.WriteLine("END live=" + link.Live + " status=" + link.Status);
            link.Stop();
            return 0;
        }
    }
}
