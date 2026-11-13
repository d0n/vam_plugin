// Identity of this Person plugin build: which character slot it serves.
//
// The second character's package (d0n.AIBodyPerson2) is generated from these sources by
// tools/make_person2.py, which rewrites the values below (slot person2, title "AIBody Person 2")
// and the namespace (AIBody2) so both scripts are distinct classes with distinct params.
namespace AIBody
{
    public static class PersonIdentity
    {
        public const string Slot = Protocol.Slot1;
        public const string Title = "AIBody Person";
        public const string Character = "character 1";
        public const string Cslist = "AIBody/AIBodyPerson.cslist";
    }
}
